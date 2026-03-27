import { useState, useRef, useCallback, useEffect, useMemo } from "react";

const RAW_API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const API_BASE = RAW_API_BASE.endsWith("/") ? RAW_API_BASE.slice(0, -1) : RAW_API_BASE;
const TABS = ["1D", "1W", "1M", "3M", "YTD", "ALL"];

// ─── Smooth bezier path ───────────────────────────────────────────────────────
function smoothPath(points) {
  if (points.length < 2) return "";
  let d = `M ${points[0].x} ${points[0].y}`;
  for (let i = 1; i < points.length; i++) {
    const prev = points[i - 1];
    const curr = points[i];
    const cpx = (prev.x + curr.x) / 2;
    d += ` C ${cpx} ${prev.y}, ${cpx} ${curr.y}, ${curr.x} ${curr.y}`;
  }
  return d;
}

// ─── X-axis label formatter ───────────────────────────────────────────────────
const LABELS = {
  "1D":  (i, n) => {
    const hours = ["9:30","10:00","10:30","11:00","11:30","12:00","12:30","1:00","1:30","2:00","2:30","3:00","3:30","4:00"];
    return hours[Math.round((i / (n - 1)) * (hours.length - 1))];
  },
  "1W":  (i, n) => ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"][Math.round((i/(n-1))*6)],
  "1M":  (i, n) => { const d = new Date(); d.setDate(d.getDate()-30+Math.round((i/(n-1))*30)); return `${d.toLocaleString("default",{month:"short"})} ${d.getDate()}`; },
  "3M":  (i, n) => { const d = new Date(); d.setDate(d.getDate()-90+Math.round((i/(n-1))*90)); return `${d.toLocaleString("default",{month:"short"})} ${d.getDate()}`; },
  "YTD": (i, n) => { const d = new Date(); d.setDate(d.getDate()-180+Math.round((i/(n-1))*180)); return d.toLocaleString("default",{month:"short"}); },
  "ALL": (i, n) => { const d = new Date(); d.setFullYear(d.getFullYear()-5+Math.round((i/(n-1))*5)); return `${d.getFullYear()}`; },
};

// ─── Skeleton bar ─────────────────────────────────────────────────────────────
function Skeleton({ width, height, style = {} }) {
  return (
    <div style={{
      width, height,
      background: "#1a1a1a",
      borderRadius: 3,
      overflow: "hidden",
      position: "relative",
      ...style,
    }}>
      <div style={{
        position: "absolute", inset: 0,
        background: "linear-gradient(90deg, transparent 0%, #2a2a2a 50%, transparent 100%)",
        animation: "shimmer 1.4s infinite",
      }} />
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────
export default function RobinhoodGraph() {
  const [tab, setTab]           = useState("1D");
  const [hoverIdx, setHoverIdx] = useState(null);
  const [animKey, setAnimKey]   = useState(0);
  const [history, setHistory]   = useState([]);
  const [contribs, setContribs] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const [warnings, setWarnings] = useState([]);
  const svgRef = useRef(null);

  // ── Fetch on tab change ──
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setWarnings([]);
    setHoverIdx(null);

    Promise.all([
      fetch(`${API_BASE}/api/portfolio?tab=${tab}`)
        .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
      fetch(`${API_BASE}/api/contributions?tab=${tab}`)
        .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); }),
    ])
      .then(([port, contrib]) => {
        if (cancelled) return;
        setHistory(port.history ?? []);
        setContribs(contrib.contributions ?? []);
        const nextWarnings = [
          port.warning ?? null,
          contrib.warning ?? null,
        ].filter(Boolean);
        setWarnings([...new Set(nextWarnings)]);
        setAnimKey(k => k + 1);
        setLoading(false);
      })
      .catch(err => {
        if (cancelled) return;
        setError(err.message);
        setLoading(false);
      });

    return () => { cancelled = true; };
  }, [tab]);

  // ── Chart geometry ──
  const W = 600, H = 200;
  const PAD = { t: 10, r: 0, b: 30, l: 0 };
  const innerW = W - PAD.l - PAD.r;
  const innerH = H - PAD.t - PAD.b;

  const minVal = useMemo(() => history.length ? Math.min(...history) : 0, [history]);
  const maxVal = useMemo(() => history.length ? Math.max(...history) : 1, [history]);
  const range  = maxVal - minVal || 1;

  const points = useMemo(() =>
    history.map((v, i) => ({
      x: PAD.l + (i / Math.max(history.length - 1, 1)) * innerW,
      y: PAD.t + innerH - ((v - minVal) / range) * innerH,
    })), [history, minVal, range]);

  const startVal   = history[0] ?? 0;
  const displayVal = hoverIdx !== null ? (history[hoverIdx] ?? startVal) : (history[history.length - 1] ?? startVal);
  const change     = displayVal - startVal;
  const changePct  = startVal ? (change / startVal) * 100 : 0;
  const isUp       = change >= 0;
  const accent     = isUp ? "#00C805" : "#FF5000";

  const linePath = useMemo(() => smoothPath(points), [points]);
  const areaPath = useMemo(() => {
    if (!points.length) return "";
    const bot = PAD.t + innerH;
    return linePath + ` L ${points[points.length-1].x} ${bot} L ${points[0].x} ${bot} Z`;
  }, [linePath, points]);

  // ── Hover handler ──
  const handleMouseMove = useCallback((e) => {
    const svg = svgRef.current;
    if (!svg || !history.length) return;
    const rect = svg.getBoundingClientRect();
    const x    = (e.clientX - rect.left) * (W / rect.width) - PAD.l;
    const idx  = Math.round((x / innerW) * (history.length - 1));
    setHoverIdx(Math.max(0, Math.min(history.length - 1, idx)));
  }, [history.length]);

  const hoverPoint   = hoverIdx !== null ? points[hoverIdx] : null;
  const labelIndices = history.length
    ? Array.from({ length: 5 }, (_, i) => Math.round((i / 4) * (history.length - 1)))
    : [];

  // ─────────────────────────────────────────────────────────────────────────────
  return (
    <div style={{
      background: "#000",
      minHeight: "100vh",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      padding: "40px 0 60px",
      fontFamily: "'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif",
    }}>
      <style>{`
        @keyframes shimmer {
          0%   { transform: translateX(-100%); }
          100% { transform: translateX(100%); }
        }
        button:focus { outline: none; }
      `}</style>

      <div style={{ width: "100%", maxWidth: 640, padding: "0 20px" }}>

        {/* ── Header ── */}
        <div style={{ marginBottom: 2, minHeight: 68 }}>
          {error ? (
            <div>
              <div style={{ color: "#FF5000", fontSize: 14, paddingTop: 8 }}>⚠ Could not connect to server</div>
              <div style={{ color: "#555", marginTop: 6, fontSize: 12, lineHeight: 1.6 }}>
                Start the backend first:<br />
                <code style={{ color: "#888" }}>python server.py</code>
              </div>
            </div>
          ) : loading ? (
            <>
              <Skeleton width={200} height={36} style={{ marginBottom: 8 }} />
              <Skeleton width={140} height={18} />
            </>
          ) : (
            <>
              <div style={{ fontSize: 36, fontWeight: 700, color: "#fff", letterSpacing: "-0.5px" }}>
                {displayVal.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 })}
              </div>
              <div style={{ fontSize: 15, fontWeight: 500, color: accent, marginTop: 2, transition: "color 0.3s" }}>
                {change >= 0 ? "+" : ""}
                {change.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 })}
                {" "}({changePct >= 0 ? "+" : ""}{changePct.toFixed(2)}%)
                {" "}
                <span style={{ color: "#888", fontWeight: 400, fontSize: 13 }}>
                  {tab === "1D" ? "Today" : tab === "ALL" ? "All time" : tab}
                </span>
              </div>
            </>
          )}
        </div>

        {!error && !loading && warnings.length > 0 && (
          <div style={{
            marginTop: 10,
            marginBottom: 8,
            padding: "10px 12px",
            borderRadius: 8,
            border: "1px solid #3a2e00",
            background: "#1a1400",
          }}>
            {warnings.map((msg) => (
              <div key={msg} style={{ color: "#f5c451", fontSize: 12, lineHeight: 1.5 }}>
                {msg}
              </div>
            ))}
          </div>
        )}

        {/* ── Chart ── */}
        <div style={{ position: "relative", marginTop: 16 }}>
          {loading ? (
            <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ display: "block" }}>
              <rect x="0" y={PAD.t} width={W} height={innerH} rx="4" fill="#0d0d0d" />
              <path
                d={`M 0 ${PAD.t + innerH * 0.6} C 150 ${PAD.t + innerH * 0.3}, 300 ${PAD.t + innerH * 0.7}, 600 ${PAD.t + innerH * 0.2}`}
                fill="none" stroke="#1a1a1a" strokeWidth="2"
              />
            </svg>
          ) : points.length > 1 ? (
            <svg
              ref={svgRef}
              viewBox={`0 0 ${W} ${H}`}
              width="100%"
              style={{ display: "block", cursor: "crosshair", overflow: "visible" }}
              onMouseMove={handleMouseMove}
              onMouseLeave={() => setHoverIdx(null)}
            >
              <defs>
                <linearGradient id={`grad-${animKey}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%"   stopColor={accent} stopOpacity="0.18" />
                  <stop offset="100%" stopColor={accent} stopOpacity="0" />
                </linearGradient>
                <clipPath id={`clip-${animKey}`}>
                  <rect x="0" y="0" width="0" height={H}>
                    <animate attributeName="width" from="0" to={W} dur="0.7s" fill="freeze"
                      calcMode="spline" keySplines="0.4 0 0.2 1" />
                  </rect>
                </clipPath>
              </defs>

              <path d={areaPath} fill={`url(#grad-${animKey})`} clipPath={`url(#clip-${animKey})`} />
              <path d={linePath} fill="none" stroke={accent} strokeWidth="1.8"
                clipPath={`url(#clip-${animKey})`} style={{ transition: "stroke 0.3s" }} />

              {hoverPoint && (
                <>
                  <line x1={hoverPoint.x} y1={PAD.t} x2={hoverPoint.x} y2={PAD.t + innerH}
                    stroke="#333" strokeWidth="1" />
                  <circle cx={hoverPoint.x} cy={hoverPoint.y} r="5"
                    fill={accent} stroke="#000" strokeWidth="2" />
                </>
              )}

              {labelIndices.map(idx => {
                const pt    = points[idx];
                const label = LABELS[tab]?.(idx, history.length) ?? "";
                const align = idx === 0 ? "start" : idx === history.length - 1 ? "end" : "middle";
                return (
                  <text key={idx} x={pt.x} y={H - 4} textAnchor={align}
                    fill="#555" fontSize="10" fontFamily="inherit">
                    {label}
                  </text>
                );
              })}
            </svg>
          ) : null}
        </div>

        {/* ── Tabs ── */}
        <div style={{
          display: "flex",
          justifyContent: "space-between",
          marginTop: 8,
          borderTop: "1px solid #1a1a1a",
          paddingTop: 12,
        }}>
          {TABS.map(t => (
            <button key={t} onClick={() => setTab(t)} disabled={loading}
              style={{
                background: "none", border: "none",
                cursor: loading ? "default" : "pointer",
                color: tab === t ? "#fff" : "#555",
                fontSize: 13, fontWeight: tab === t ? 600 : 400,
                fontFamily: "inherit", padding: "6px 12px", borderRadius: 20,
                backgroundColor: tab === t ? "#1a1a1a" : "transparent",
                transition: "all 0.15s", letterSpacing: "0.3px",
                opacity: loading ? 0.4 : 1,
              }}
            >{t}</button>
          ))}
        </div>

        {/* ── Divider ── */}
        <div style={{ height: 1, background: "#1a1a1a", margin: "28px 0 20px" }} />

        {/* ── Top Movers ── */}
        <div>
          <div style={{ fontSize: 17, fontWeight: 600, color: "#fff", marginBottom: 16 }}>
            Top movers
          </div>

          {loading ? (
            [1, 0.85, 0.7, 0.55, 0.4].map((op, i) => (
              <div key={i} style={{ display: "flex", alignItems: "center", marginBottom: 14, gap: 12, opacity: op }}>
                <Skeleton width={44} height={14} />
                <div style={{ flex: 1 }}><Skeleton width="100%" height={6} /></div>
                <Skeleton width={72} height={14} />
              </div>
            ))
          ) : contribs.length === 0 ? (
            <div style={{ color: "#555", fontSize: 13 }}>No position data available.</div>
          ) : (
            contribs.map(({ s, c }) => {
              const isPos  = c >= 0;
              const barMax = Math.max(...contribs.map(x => Math.abs(x.c)));
              const barW   = (Math.abs(c) / barMax) * 100;
              return (
                <div key={s} style={{ display: "flex", alignItems: "center", marginBottom: 14, gap: 12 }}>
                  <div style={{ width: 44, fontSize: 14, fontWeight: 600, color: "#fff", flexShrink: 0 }}>{s}</div>
                  <div style={{ flex: 1, position: "relative", height: 6, background: "#1a1a1a", borderRadius: 3, overflow: "hidden" }}>
                    <div style={{
                      position: "absolute", left: 0, top: 0, bottom: 0,
                      width: `${barW}%`,
                      background: isPos ? "#00C805" : "#FF5000",
                      borderRadius: 3,
                      transition: "width 0.5s cubic-bezier(0.4,0,0.2,1), background 0.3s",
                    }} />
                  </div>
                  <div style={{
                    width: 72, fontSize: 14, fontWeight: 500,
                    textAlign: "right", flexShrink: 0,
                    color: isPos ? "#00C805" : "#FF5000",
                  }}>
                    {isPos ? "+" : ""}
                    {c.toLocaleString("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 })}
                  </div>
                </div>
              );
            })
          )}
        </div>

        <div style={{ marginTop: 32, fontSize: 11, color: "#2a2a2a", lineHeight: 1.6 }}>
          Past performance does not guarantee future results.
        </div>
      </div>
    </div>
  );
}
