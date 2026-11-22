"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, AlertTriangle, ArrowUpRight, BrainCircuit, CalendarDays,
  CheckCircle2, ChevronDown, CloudRain, Database, Gauge, HeartPulse,
  Layers3, MapPin, RefreshCw, ShieldCheck, SlidersHorizontal,
  Thermometer, Wind, Zap,
} from "lucide-react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";

type Meta = {
  dataset: {
    rows: number;
    wards: number;
    cities: string[];
    start_date: string;
    end_date: string;
    missing_values: number;
    duplicate_ward_dates: number;
  };
  models: Record<string, {
    selected_model: string;
    validation: { mae: number; rmse: number; samples: number };
    test: { mae: number; rmse: number; samples: number };
    baseline_test: { mae: number; rmse: number; samples: number };
  }>;
  latest_date: string;
};
type Ward = { city: string; ward_id: string };
type Prediction = {
  city: string;
  ward_id: string;
  horizon_weeks: number;
  reference_date: string;
  forecast_target_date: string;
  predicted_cases: number;
  risk_level: string;
  risk_thresholds: Record<string, number>;
  weather_inputs: Record<string, number>;
  risk_drivers: { driver: string; status: string; explanation: string }[];
  model_name: string;
  data_note: string;
  prediction_id?: string;
};
type Metrics = {
  model: Record<string, unknown>;
  feature_importance: { feature: string; importance: number }[];
};
type ApiCities = { cities: string[] };
type ApiWards = { wards: Ward[] };

const API = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
const riskClass: Record<string, string> = {
  LOW: "low", MEDIUM: "medium", HIGH: "high", CRITICAL: "critical",
};

async function readApi<T>(response: Response): Promise<T> {
  const raw = await response.text();
  let data: unknown = null;
  try {
    data = raw ? JSON.parse(raw) : null;
  } catch {
    throw new Error("The backend returned an invalid response. Check the API server logs.");
  }

  if (!response.ok) {
    const detail = data && typeof data === "object" && "detail" in data
      ? String((data as { detail: unknown }).detail)
      : `Request failed (${response.status}).`;
    throw new Error(detail);
  }
  return data as T;
}

function formatNumber(value: number | undefined, digits = 1) {
  return typeof value !== "number" || !Number.isFinite(value)
    ? "—"
    : value.toLocaleString(undefined, { maximumFractionDigits: digits });
}

export default function DashboardPage() {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [cities, setCities] = useState<string[]>([]);
  const [wards, setWards] = useState<Ward[]>([]);
  const [city, setCity] = useState("Chattogram");
  const [wardId, setWardId] = useState("CCC_Ward_01");
  const [horizon, setHorizon] = useState<2 | 4>(4);
  const [asOfDate, setAsOfDate] = useState("");
  const [scenario, setScenario] = useState(false);
  const [rainfall, setRainfall] = useState("0");
  const [temperature, setTemperature] = useState("28");
  const [humidity, setHumidity] = useState("75");
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(false);
  const [booting, setBooting] = useState(true);
  const [error, setError] = useState("");
  const [apiOnline, setApiOnline] = useState(false);

  // Load static dashboard data once. Changing city must not refetch metadata.
  const loadMeta = useCallback(async () => {
    setBooting(true);
    setError("");
    try {
      const [m, c, w] = await Promise.all([
        fetch(`${API}/meta`, { cache: "no-store" }).then(readApi<Meta>),
        fetch(`${API}/cities`, { cache: "no-store" }).then(readApi<ApiCities>),
        fetch(`${API}/wards`, { cache: "no-store" }).then(readApi<ApiWards>),
      ]);

      if (!Array.isArray(c.cities) || !Array.isArray(w.wards)) {
        throw new Error("The backend returned an unexpected cities/wards response.");
      }

      setMeta(m);
      setCities(c.cities);
      setWards(w.wards);
      setCity(current => c.cities.includes(current) ? current : (c.cities[0] ?? ""));
      setAsOfDate(current => {
        const inRange = current && current >= m.dataset.start_date && current <= m.dataset.end_date;
        return inRange ? current : m.latest_date;
      });
      setApiOnline(true);
    } catch (e) {
      setApiOnline(false);
      setError(e instanceof TypeError
        ? "Cannot reach the backend. Start the FastAPI server in a separate terminal, then refresh."
        : e instanceof Error ? e.message : "Could not load dashboard data.");
    } finally {
      setBooting(false);
    }
  }, []);

  useEffect(() => { void loadMeta(); }, [loadMeta]);

  const filteredWards = useMemo(
    () => wards.filter(w => w.city === city),
    [wards, city],
  );

  useEffect(() => {
    if (!filteredWards.length) {
      setWardId("");
      return;
    }
    if (!filteredWards.some(w => w.ward_id === wardId)) {
      setWardId(filteredWards[0].ward_id);
    }
  }, [filteredWards, wardId]);

  const loadMetrics = useCallback(async () => {
    try {
      const response = await fetch(`${API}/metrics?horizon_weeks=${horizon}`, { cache: "no-store" });
      const result = await readApi<Metrics>(response);
      setMetrics(result);
    } catch {
      // Model metrics are supplementary; the prediction workflow remains available.
      setMetrics(null);
    }
  }, [horizon]);

  useEffect(() => { void loadMetrics(); }, [loadMetrics]);

  async function runPrediction() {
    if (!apiOnline) {
      setError("The API is offline. Start the backend first.");
      return;
    }
    if (!city || !wardId) {
      setError("Select a city and ward before generating a forecast.");
      return;
    }

    const weatherValues = [Number(rainfall), Number(temperature), Number(humidity)];
    if (scenario && (
      weatherValues.some(value => !Number.isFinite(value)) ||
      weatherValues[0] < 0 || weatherValues[0] > 1000 ||
      weatherValues[1] < 0 || weatherValues[1] > 55 ||
      weatherValues[2] < 0 || weatherValues[2] > 100
    )) {
      setError("Check the weather inputs: rainfall 0–1000 mm, temperature 0–55°C and humidity 0–100%.");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const body: Record<string, unknown> = {
        city,
        ward_id: wardId,
        horizon_weeks: horizon,
        ...(asOfDate ? { as_of_date: asOfDate } : {}),
      };
      if (scenario) {
        body.weather_override = {
          rainfall_mm: weatherValues[0],
          avg_temp_c: weatherValues[1],
          relative_humidity_pct: weatherValues[2],
        };
      }

      const response = await fetch(`${API}/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const result = await readApi<Prediction>(response);
      setPrediction(result);
    } catch (e) {
      setError(e instanceof TypeError
        ? "The prediction request could not reach the API. Check that the backend is running."
        : e instanceof Error ? e.message : "Prediction failed. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  const metricForHorizon = meta?.models[String(horizon)];
  const weatherChart = prediction ? [
    { name: "Weekly rainfall", rainfall: prediction.weather_inputs.rainfall_mm },
    { name: "2-week total", rainfall: prediction.weather_inputs.rainfall_sum_2w },
    { name: "4-week total", rainfall: prediction.weather_inputs.rainfall_sum_4w },
  ].filter(item => Number.isFinite(item.rainfall)) : [];

  return (
    <main className="app-shell" id="top">
      <aside className="sidebar">
        <div className="brand-lockup">
          <div className="brand-mark"><HeartPulse size={21} /></div>
          <div><strong>DengueShield</strong><span>WARD RISK OUTLOOK</span></div>
        </div>
        <div className="nav-label">WORKSPACE</div>
        <a className="nav-item active" href="#top"><Layers3 size={17} /> Overview</a>
        <a className="nav-item" href="#forecast"><Activity size={17} /> Risk forecast</a>
        <a className="nav-item" href="#model"><BrainCircuit size={17} /> Model insights</a>
        <div className="sidebar-bottom">
          <div className="secure-card"><ShieldCheck size={18} /><div><b>Research prototype</b><span>Decision support, not diagnosis</span></div></div>
          <span className="side-foot">EDU AI Engineering Hackathon 2026</span>
        </div>
      </aside>

      <section className="main-area">
        <header className="topbar">
          <div><div className="eyebrow">PUBLIC HEALTH INTELLIGENCE / BANGLADESH</div><h1>Outbreak intelligence</h1></div>
          <div className="top-actions">
            <span className={`connection ${apiOnline ? "online" : "offline"}`}><i />{apiOnline ? "API connected" : "API offline"}</span>
            <button className="icon-button" type="button" onClick={() => void loadMeta()} aria-label="Refresh dashboard" disabled={booting}><RefreshCw size={17} className={booting ? "spin" : ""} /></button>
            <div className="avatar">DS</div>
          </div>
        </header>

        <div className="content-wrap">
          <section className="hero-panel">
            <div className="hero-copy">
              <div className="hero-kicker"><ShieldCheck size={14} /> DENGUE SURVEILLANCE / BANGLADESH</div>
              <h2>Local signals.<br /><em>Clearer decisions.</em></h2>
              <p>Explore ward-level dengue forecasts using historical case records, weather patterns and local vulnerability indicators.</p>
              <div className="hero-tags"><span><MapPin size={13} /> Ward-level coverage</span><span><CalendarDays size={13} /> 2- and 4-week outlooks</span></div>
            </div>
            <div className="hero-side-note">
              <span>FORECAST HORIZONS</span>
              <strong>02 <i>/</i> 04</strong>
              <small>weeks ahead</small>
              <div>Historical data · Model-based estimates</div>
            </div>
          </section>

          <section className="stat-grid">
            <div className="stat-card"><div className="stat-top"><span>Historical observations</span><Database size={17} /></div><strong>{meta ? meta.dataset.rows.toLocaleString() : "—"}</strong><small>Weekly ward records</small></div>
            <div className="stat-card"><div className="stat-top"><span>Coverage</span><MapPin size={17} /></div><strong>{meta ? `${meta.dataset.wards} wards` : "—"}</strong><small>{meta ? `${meta.dataset.cities.length} cities` : "Dataset coverage"}</small></div>
            <div className="stat-card"><div className="stat-top"><span>Data period</span><CalendarDays size={17} /></div><strong className="date-stat">{meta ? `${meta.dataset.start_date.slice(0, 4)} — ${meta.dataset.end_date.slice(0, 4)}` : "—"}</strong><small>Historical dataset range</small></div>
            <div className="stat-card"><div className="stat-top"><span>Data quality</span><CheckCircle2 size={17} /></div><strong>{meta ? (meta.dataset.missing_values === 0 && meta.dataset.duplicate_ward_dates === 0 ? "Verified" : "Review") : "—"}</strong><small>{meta ? `${meta.dataset.missing_values} missing · ${meta.dataset.duplicate_ward_dates} duplicates` : "Missing & duplicate checks"}</small></div>
          </section>

          <div className="section-heading" id="forecast">
            <div><div className="eyebrow">FORECAST CONFIGURATION</div><h3>Generate a ward-level outlook</h3><p>Choose a location and reference week to run the trained model.</p></div>
            <span className="model-pill"><Zap size={14} /> Local model inference</span>
          </div>

          <section className="workspace-grid">
            <div className="panel input-panel">
              <div className="panel-title"><div className="panel-icon"><SlidersHorizontal size={17} /></div><div><h4>Prediction inputs</h4><p>Configure your forecast</p></div></div>
              <div className="form-grid">
                <label>City<select value={city} onChange={e => { setCity(e.target.value); setPrediction(null); }} disabled={booting || !cities.length}><option value="">Select city</option>{cities.map(c => <option key={c} value={c}>{c}</option>)}</select><ChevronDown className="select-chevron" size={14} /></label>
                <label>Ward<select value={wardId} onChange={e => { setWardId(e.target.value); setPrediction(null); }} disabled={booting || !filteredWards.length}><option value="">Select ward</option>{filteredWards.map(w => <option key={w.ward_id} value={w.ward_id}>{w.ward_id}</option>)}</select><ChevronDown className="select-chevron" size={14} /></label>
                <label>Reference week<input type="date" value={asOfDate} min={meta?.dataset.start_date} max={meta?.dataset.end_date} onChange={e => { setAsOfDate(e.target.value); setPrediction(null); }} disabled={!meta} /></label>
                <label>Forecast horizon<select value={horizon} onChange={e => { setHorizon(Number(e.target.value) as 2 | 4); setPrediction(null); }}><option value={2}>2 weeks ahead</option><option value={4}>4 weeks ahead</option></select><ChevronDown className="select-chevron" size={14} /></label>
              </div>
              <div className="scenario-toggle"><div><b>Weather scenario override</b><span>Test a what-if scenario for the selected reference week.</span></div><button type="button" className={`toggle ${scenario ? "on" : ""}`} onClick={() => setScenario(value => !value)} aria-label="Toggle weather override" aria-pressed={scenario}><i /></button></div>
              {scenario && <div className="form-grid scenario-grid">
                <label><span><CloudRain size={13} /> Rainfall (mm)</span><input type="number" min="0" max="1000" step="0.1" value={rainfall} onChange={e => setRainfall(e.target.value)} /></label>
                <label><span><Thermometer size={13} /> Avg. temperature (°C)</span><input type="number" min="0" max="55" step="0.1" value={temperature} onChange={e => setTemperature(e.target.value)} /></label>
                <label><span><Wind size={13} /> Humidity (%)</span><input type="number" min="0" max="100" step="0.1" value={humidity} onChange={e => setHumidity(e.target.value)} /></label>
              </div>}
              <button className="primary-button" type="button" onClick={runPrediction} disabled={loading || booting || !apiOnline || !wardId}>
                {loading ? <><RefreshCw className="spin" size={16} /> Running model…</> : <><Activity size={17} /> Generate risk forecast <ArrowUpRight size={16} /></>}
              </button>
              {error && <div className="error-box" role="alert"><AlertTriangle size={16} /><span>{error}</span></div>}
              <div className="input-footnote"><ShieldCheck size={14} /> Forecasts are research estimates based on the supplied historical dataset.</div>
            </div>

            <div className="panel result-panel">
              <div className="panel-title"><div className="panel-icon result-icon"><Gauge size={17} /></div><div><h4>Forecast result</h4><p>{prediction ? `${prediction.city} · ${prediction.ward_id}` : "Your forecast will appear here"}</p></div></div>
              {prediction ? <>
                <div className="result-main">
                  <div><span className="result-label">ESTIMATED CASE COUNT</span><div className="big-number">{formatNumber(prediction.predicted_cases, 1)}<small> cases</small></div><span className="result-date">Target week · {prediction.forecast_target_date}</span></div>
                  <span className={`risk-badge ${riskClass[prediction.risk_level] || "neutral"}`}><i />{prediction.risk_level} RISK</span>
                </div>
                <div className="result-meta">
                  <span><MapPin size={14} />{prediction.city} / {prediction.ward_id}</span>
                  <span><CalendarDays size={14} />Reference · {prediction.reference_date}</span>
                  <span>{prediction.horizon_weeks}-week horizon</span>
                </div>
                <div className="result-model"><span>Model</span><strong>{prediction.model_name}</strong></div>
                <div className="threshold-strip">
                  <span>LOW ≤ {formatNumber(prediction.risk_thresholds.low_max, 1)}</span>
                  <span>MEDIUM ≤ {formatNumber(prediction.risk_thresholds.medium_max, 1)}</span>
                  <span>HIGH ≤ {formatNumber(prediction.risk_thresholds.high_max, 1)}</span>
                  <span>CRITICAL above</span>
                </div>
                <small className="risk-note">Risk category uses the unrounded model output; the case estimate is rounded for display.</small>
                <div className="driver-list"><b>Signals to review</b>{prediction.risk_drivers.map((d, i) => <div className="driver-item" key={`${d.driver}-${i}`}><span className={`driver-dot ${d.status}`} /><div><strong>{d.driver}</strong><small>{d.explanation}</small></div></div>)}</div>
              </> : <div className="empty-result"><div className="empty-orb"><Activity size={27} /></div><b>{booting ? "Loading dataset" : loading ? "Generating forecast" : "No forecast generated"}</b><span>{apiOnline ? "Select a city, ward and reference week, then generate a forecast to review the estimated cases and risk category." : "Start the backend API to load the dataset and enable ward-level predictions."}</span><div className="empty-mini"><span>2-week model</span><span>4-week model</span></div></div>}
            </div>
          </section>

          {prediction && <section className="insight-grid">
            <div className="panel"><div className="panel-title"><div className="panel-icon"><CloudRain size={17} /></div><div><h4>Weather signal breakdown</h4><p>Current and accumulated rainfall inputs</p></div></div><div className="chart-wrap"><ResponsiveContainer width="100%" height={220}><AreaChart data={weatherChart} margin={{ top: 10, right: 12, left: -18, bottom: 0 }}><defs><linearGradient id="rainFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#4b927d" stopOpacity={0.2} /><stop offset="100%" stopColor="#4b927d" stopOpacity={0.01} /></linearGradient></defs><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e8eeeb" /><XAxis dataKey="name" tick={{ fill: "#84928c", fontSize: 11 }} /><YAxis tick={{ fill: "#84928c", fontSize: 11 }} /><Tooltip /><Area type="monotone" dataKey="rainfall" stroke="#397d69" fill="url(#rainFill)" strokeWidth={2} /></AreaChart></ResponsiveContainer></div></div>
            <div className="panel weather-panel"><div className="panel-title"><div className="panel-icon"><Thermometer size={17} /></div><div><h4>Selected weather inputs</h4><p>Conditions used for this forecast</p></div></div><div className="weather-stats"><div><span>Temperature</span><b>{formatNumber(prediction.weather_inputs.avg_temp_c)}°C</b></div><div><span>Rainfall</span><b>{formatNumber(prediction.weather_inputs.rainfall_mm)} mm</b></div><div><span>Humidity</span><b>{formatNumber(prediction.weather_inputs.relative_humidity_pct)}%</b></div><div><span>4-week rainfall</span><b>{formatNumber(prediction.weather_inputs.rainfall_sum_4w)} mm</b></div></div></div>
          </section>}

          <section className="section-heading model-heading" id="model"><div><div className="eyebrow">MODEL TRANSPARENCY</div><h3>Performance & methodology</h3><p>Chronological holdout evaluation on the supplied historical dataset.</p></div></section>
          <section className="model-grid">
            <div className="panel performance-panel"><div className="panel-title"><div className="panel-icon"><Gauge size={17} /></div><div><h4>{horizon}-week model performance</h4><p>Final test period · 2025</p></div></div><div className="performance-stats"><div><span>Test MAE</span><strong>{metricForHorizon ? formatNumber(metricForHorizon.test.mae, 3) : "—"}</strong><small>Mean absolute error</small></div><div><span>Test RMSE</span><strong>{metricForHorizon ? formatNumber(metricForHorizon.test.rmse, 3) : "—"}</strong><small>Root mean squared error</small></div><div><span>Baseline MAE</span><strong>{metricForHorizon ? formatNumber(metricForHorizon.baseline_test.mae, 3) : "—"}</strong><small>Median baseline</small></div></div><div className="method-note"><CheckCircle2 size={15} /> Time-ordered split: train through 2023, validate on 2024, test on 2025. Test data was not used for model selection.</div></div>
            <div className="panel importance-panel"><div className="panel-title"><div className="panel-icon"><Activity size={17} /></div><div><h4>Global model drivers</h4><p>Top features by model importance</p></div></div>{metrics?.feature_importance?.length ? <div className="importance-chart"><ResponsiveContainer width="100%" height={240}><BarChart data={metrics.feature_importance.slice(0, 7)} layout="vertical" margin={{ top: 2, right: 16, left: 12, bottom: 2 }}><CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e8eeeb" /><XAxis type="number" hide /><YAxis type="category" dataKey="feature" width={126} tick={{ fill: "#718078", fontSize: 10 }} /><Tooltip /><Bar dataKey="importance" radius={[0, 4, 4, 0]}>{metrics.feature_importance.slice(0, 7).map((_, i) => <Cell key={i} fill={i === 0 ? "#356d5c" : "#86a99b"} />)}</Bar></BarChart></ResponsiveContainer></div> : <div className="empty-small">Model feature importance will appear when the API is available.</div>}</div>
          </section>

          <section className="notice-panel"><div className="notice-icon"><AlertTriangle size={18} /></div><div><b>Important data limitation</b><p>{prediction?.data_note || `The supplied dataset covers ${meta?.dataset.start_date || "the historical period"} to ${meta?.dataset.end_date || "the latest available date"}. Forecasts are anchored to a selected historical reference week; this build does not fetch live weather or official current case counts. Treat outputs as research decision-support estimates, not clinical or operational instructions.`}</p></div></section>
          <footer className="footer"><span>© 2026 DengueShield AI · EDU AI Engineering Hackathon</span><span>Built for SDG 3 & SDG 10</span></footer>
        </div>
      </section>
    </main>
  );
}
