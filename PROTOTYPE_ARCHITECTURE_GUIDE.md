# Prototype Architecture Guide

This document describes how to build **local prototypes** that can be smoothly converted into production visualizers on the Astrolabe Data Visualization Platform. Follow these patterns during rapid local development to ensure your work transfers cleanly without rework.

> **Audience:** AI agents assisting with local prototype development. The goal is fast iteration on your machine, with output that Astrolabe can ingest directly.

---

## Quick Reference

| Aspect | Local Prototype | Production Visualizer |
|--------|-----------------|----------------------|
| Framework | React + Vite | React 18 + Vite |
| Styling | CSS Modules (`.module.css`) | CSS Modules (`.module.css`) |
| Charts | Recharts | Recharts |
| Icons | Lucide React | Lucide React |
| Data Storage | Local JSON files (normalized structure) | S3 analytics folder |
| Data Generation | Python scripts → JSON | Same scripts, output to S3 |

---

## 1. Overview: Your Workflow

This is the typical development workflow:

1. **Download raw data** - You receive a zipped dataset (CSVs, JSON exports, etc.)
2. **Analyze locally** - Explore the data, build analytics scripts, iterate on insights
3. **Build prototype** - Create a React dashboard that showcases your analysis
4. **Push to git** - Upload your prototype repository
5. **Handoff** - Astrolabe pulls your repo and integrates it into production

The key to smooth handoff is **following the patterns in this guide** so your prototype transfers cleanly without rework.

### 1.1 Local Prototype Structure

Your local prototype should be a standalone repository with this structure:

```
my-fleet-prototype/
├── index.html                    # Vite entry point
├── package.json                  # React, Recharts, Lucide, Vite
├── vite.config.js
├── src/
│   ├── App.jsx                   # Main dashboard
│   ├── components/               # React components
│   │   ├── FleetDashboard.jsx
│   │   ├── FleetDashboard.module.css
│   │   ├── BatteryDetail.jsx
│   │   └── BatteryDetail.module.css
│   └── styles/
│       └── variables.css
├── analytics/                    # ← Generated JSON output (mirrors S3)
│   ├── fleet/
│   │   ├── fleet_summary.json
│   │   ├── fleet_utilization.json
│   │   └── fleet_temperature.json
│   ├── batteries/
│   │   ├── {sn1}.json
│   │   └── {sn2}.json
│   └── temperature/
│       ├── fleet_temperature.json
│       └── {sn}.json
├── generate_fleet_summary.py     # Analytics generation scripts
├── generate_temperature.py
├── generate_utilization.py
└── raw_data/                     # Source data (CSV, Parquet, DB exports)
    └── *.csv
```

### 1.2 What Goes in Your Git Repository

| Include | Reason |
|---------|--------|
| `src/` (React components) | Dashboard UI |
| Python scripts | Generate analytics from data |
| `package.json`, `vite.config.js` | Project setup |
| `README.md` | How to run locally |
| `.gitignore` | Exclude large files |

| Exclude from Git (but hand off separately) | Reason |
|---------------------------------------------|--------|
| `raw_data/` | Too large, provide download link or share separately |
| `local.db` (if used) | Required if scripts depend on it—share via cloud storage |
| `analytics/` | Generated output, can be regenerated |
| `node_modules/` | Installed from package.json |

---

## 2. Data Architecture (Critical for Handoff)

### 2.1 The Data Pipeline

Your prototype will typically follow this pipeline:

```
RAW DATA (zipped files you received)
    ↓  (1) ETL script - one time
LOCAL DATABASE (SQLite - for efficient querying)
    ↓  (2) Analytics scripts - run as needed
ANALYTICS FOLDER (JSON files - served to frontend)
    ↓  (3) Vite serves as static files
REACT FRONTEND (fetches JSON, renders charts)
```

**The frontend never talks to the database.** It only fetches pre-generated JSON files. This is the key architectural pattern.

### 2.2 Step 1: ETL (Raw Data → Database)

When you receive a large dataset (GBs of CSVs or JSON), load it into SQLite once:

```python
# etl_to_sqlite.py - run once when you get new data
import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = "data/local.db"
RAW_DATA = Path("raw_data")

def main():
    conn = sqlite3.connect(DB_PATH)
    
    for csv_file in RAW_DATA.glob("*.csv"):
        print(f"Loading {csv_file}...")
        # Load in chunks to avoid memory issues
        for chunk in pd.read_csv(csv_file, chunksize=100_000):
            chunk.to_sql("telemetry", conn, if_exists="append", index=False)
    
    # Create indexes for fast queries
    print("Creating indexes...")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_sn ON telemetry(battery_sn)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON telemetry(timestamp)")
    conn.commit()
    print(f"Done. Database: {DB_PATH}")

if __name__ == "__main__":
    main()
```

**Why SQLite?**
- Handles GBs of data without loading into memory
- SQL makes aggregation logic easy to iterate
- Indexed queries run in milliseconds
- Single file, easy to share

### 2.3 Step 2: Analytics Scripts (Database → JSON)

Each analytics script queries the database and outputs JSON to `analytics/`:

```python
# generate_fleet_temperature.py
import sqlite3
import json
from pathlib import Path

DB_PATH = "data/local.db"
OUTPUT_PATH = Path("analytics/fleet_temperature.json")

def main():
    conn = sqlite3.connect(DB_PATH)
    
    # Fast aggregation query
    result = conn.execute("""
        SELECT battery_sn,
               COUNT(*) as total_samples,
               AVG(temperature) as avg_temp,
               MAX(temperature) as max_temp,
               SUM(CASE WHEN temperature > 113 THEN 1 ELSE 0 END) as hot_samples
        FROM telemetry
        GROUP BY battery_sn
    """).fetchall()
    
    batteries = []
    for r in result:
        batteries.append({
            "sn": r[0],
            "samples": r[1],
            "avgTemp": round(r[2], 1),
            "maxTemp": round(r[3], 1),
            "pctHot": round(100 * r[4] / r[1], 1) if r[1] > 0 else 0
        })
    
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps({"batteries": batteries}, indent=2))
    print(f"Wrote {OUTPUT_PATH}")

if __name__ == "__main__":
    main()
```

**Output to `analytics/` folder** - configure Vite to serve this as static files.

### 2.4 Step 3: Frontend Fetching

The React frontend fetches JSON from `analytics/` (served by Vite):

```jsx
useEffect(() => {
  Promise.all([
    fetch('/fleet_data.json').then(res => res.json()),
    fetch('/fleet_temperature.json').then(res => res.json()),
    fetch('/fleet_utilization.json').then(res => res.json())
  ])
    .then(([fleetData, tempData, utilData]) => {
      setData(fleetData);
      setTempData(tempData);
      setUtilizationData(utilData);
    })
    .catch(err => setError(err.message))
    .finally(() => setLoading(false));
}, []);
```

Configure Vite to serve `analytics/` as static files:

```javascript
// vite.config.js
export default defineConfig({
  plugins: [react()],
  publicDir: 'analytics'  // Serve analytics/ instead of default public/
});
```

### 2.5 Folder Structure

```
my-prototype/
├── data/
│   └── local.db              # SQLite database (gitignored)
├── raw_data/
│   └── *.csv                 # Original data (gitignored)
├── analytics/                # ← Generated JSON (served by Vite)
│   ├── fleet_data.json
│   ├── fleet_temperature.json
│   ├── fleet_utilization.json
│   ├── batteries/
│   │   ├── 18510.json
│   │   └── 18540.json
│   └── temperature/
│       ├── 18510.json
│       └── 18540.json
├── etl_to_sqlite.py          # One-time data loading
├── generate_dashboard_data.py
├── generate_fleet_temperature.py
├── generate_utilization.py
├── src/
│   ├── App.jsx
│   └── FleetDashboard.jsx
└── package.json
```

### 2.6 What Gets Handed Off

| Include in Git | Share Separately | Gitignore |
|----------------|------------------|-----------|
| `src/` (React) | `data/local.db` (if large) | `node_modules/` |
| Python scripts | `raw_data/` (or download link) | `raw_data/` |
| `package.json` | | `data/*.db` |
| `analytics/*.json` (optional) | | |

**Important:** If your scripts read from SQLite, you must share the database file. Without it, the analytics scripts can't regenerate the JSON.

---

## 3. Styling Architecture

### 3.1 CSS Modules (Required)

All component styles must use CSS Modules. This ensures complete isolation when integrated into the platform.

**File naming convention:**
```
ComponentName.module.css
```

**Usage in React:**
```jsx
import styles from './FleetDashboard.module.css';

function FleetDashboard() {
  return (
    <div className={styles.container}>
      <h1 className={styles.title}>Fleet Overview</h1>
      <div className={styles.grid}>
        {/* content */}
      </div>
    </div>
  );
}
```

### 3.2 Why CSS Modules

CSS Modules provide:

| Benefit | Description |
|---------|-------------|
| Automatic scoping | Class names are hashed at build time, preventing collisions |
| Explicit dependencies | Styles are imported like any other module |
| Zero runtime cost | Styles are extracted at build time |
| Vite native support | No additional plugins or configuration required |

### 3.3 Style Organization

Each prototype should have its own `styles/variables.css` for design tokens:

```css
/* src/styles/variables.css */
:root {
  /* Prefix with your project name to avoid future conflicts */
  --myfleet-primary: #2563eb;
  --myfleet-success: #16a34a;
  --myfleet-warning: #ca8a04;
  --myfleet-danger: #dc2626;
  
  /* Spacing */
  --myfleet-space-1: 0.25rem;
  --myfleet-space-2: 0.5rem;
  --myfleet-space-4: 1rem;
  --myfleet-space-6: 1.5rem;
  
  /* Typography */
  --myfleet-font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --myfleet-font-mono: 'SF Mono', 'Fira Code', monospace;
}
```

Import at the top of your module CSS files:

```css
/* FleetDashboard.module.css */
@import './styles/variables.css';

.container {
  padding: var(--myfleet-space-4);
  font-family: var(--myfleet-font-sans);
}
```

### 3.4 Conditional Styling

For conditional classes, use template literals:

```jsx
<button 
  className={`${styles.tab} ${isActive ? styles.tabActive : ''}`}
>
  Fleet
</button>
```

---

## 4. Component Patterns

### 4.1 Dashboard Component

```jsx
import { useState, useEffect } from 'react';
import { Battery, LayoutDashboard } from 'lucide-react';
import FleetOverview from './components/FleetOverview';
import BatteryDetail from './components/BatteryDetail';
import styles from './components/App.module.css';

const VIEWS = {
  FLEET: 'fleet',
  BATTERY: 'battery'
};

function App() {
  const [currentView, setCurrentView] = useState(VIEWS.FLEET);
  const [selectedBattery, setSelectedBattery] = useState(null);
  const [fleetData, setFleetData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Fetch from local analytics folder
    fetch('/analytics/fleet/fleet_summary.json')
      .then(res => res.json())
      .then(setFleetData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleSelectBattery = (sn) => {
    setSelectedBattery(sn);
    setCurrentView(VIEWS.BATTERY);
  };

  const handleBackToFleet = () => {
    setCurrentView(VIEWS.FLEET);
    setSelectedBattery(null);
  };

  if (loading) {
    return <div className={styles.loading}>Loading...</div>;
  }

  return (
    <div className={styles.container}>
      <header className={styles.header}>
        <h1><Battery /> My Fleet Dashboard</h1>
      </header>
      
      {currentView === VIEWS.FLEET && (
        <FleetOverview 
          data={fleetData} 
          onSelectBattery={handleSelectBattery}
        />
      )}
      
      {currentView === VIEWS.BATTERY && (
        <BatteryDetail 
          batteryId={selectedBattery}
          onBack={handleBackToFleet}
        />
      )}
    </div>
  );
}

export default App;
```

### 4.2 Chart Components with Recharts

**Interpolation:** Always use `type="linear"` on `<Line>` and `<Area>` components. This draws straight lines between data points. Do **not** use `type="monotone"` (cubic spline) — it visually smooths the data and can misrepresent actual readings.

```jsx
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';
import styles from './TemperatureChart.module.css';

function TemperatureChart({ data }) {
  return (
    <div className={styles.chartContainer}>
      <h3 className={styles.chartTitle}>Temperature Over Time</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis 
            dataKey="timestamp" 
            tickFormatter={(ts) => new Date(ts).toLocaleDateString()}
          />
          <YAxis unit="°C" />
          <Tooltip />
          <Legend />
          <Line 
            type="linear" 
            dataKey="temperature" 
            stroke="#2563eb" 
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
```

### 4.3 Status Indicators

Use consistent color coding for health/status:

```javascript
const STATUS_COLORS = {
  healthy: '#16a34a',   // Green
  monitor: '#ca8a04',   // Yellow
  warning: '#ea580c',   // Orange  
  critical: '#dc2626',  // Red
  unknown: '#6b7280'    // Gray
};

function StatusBadge({ status }) {
  return (
    <span 
      className={styles.badge}
      style={{ backgroundColor: STATUS_COLORS[status] || STATUS_COLORS.unknown }}
    >
      {status}
    </span>
  );
}
```

---

## 5. Required Dependencies

Use these exact dependencies for compatibility:

```json
{
  "dependencies": {
    "react": "^18.x",
    "react-dom": "^18.x",
    "recharts": "^2.x",
    "lucide-react": "^0.x"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.x",
    "vite": "^5.x"
  }
}
```

For icons, use Lucide React:

```jsx
import { Battery, Thermometer, Activity, AlertTriangle } from 'lucide-react';

<Battery className={styles.icon} />
<Thermometer size={16} />
```

---

## 6. Checklist for Prototype Handoff

Before pushing your prototype to git:

### Git Repository Contents
- [ ] `src/` with React components using CSS Modules
- [ ] Python analytics scripts (ETL + generate scripts)
- [ ] `package.json` with compatible dependencies
- [ ] `README.md` explaining how to run locally
- [ ] `.gitignore` excluding `node_modules/`, `data/*.db`, `raw_data/`

### Shared Separately (cloud storage, not git)
- [ ] Raw data files (or download link in README)
- [ ] SQLite database if scripts depend on it
- [ ] Any large assets

### Python Scripts
- [ ] ETL script loads raw data into SQLite (if using database)
- [ ] Analytics scripts generate JSON to `analytics/` folder
- [ ] Scripts output to correct paths (fleet_data.json, batteries/, etc.)
- [ ] Generated JSON matches what React components fetch
- [ ] Dependencies documented (requirements.txt or comments)

### React Components
- [ ] Uses CSS Modules for all styling (`.module.css` files)
- [ ] CSS variables prefixed with project name
- [ ] Uses Recharts for data visualization
- [ ] Uses Lucide React for icons
- [ ] No global CSS that would conflict with platform
- [ ] Includes loading and error states
- [ ] Fetches from `/filename.json` (Vite serves `analytics/` via publicDir config)

### Project Structure
- [ ] Clean separation: `src/`, `analytics/`, `data/`, `raw_data/`
- [ ] `package.json` with compatible dependencies
- [ ] README explaining the data pipeline and how to run locally
- [ ] Database and raw data are gitignored, shared separately

---

## 7. Example: Minimal Prototype

A complete minimal prototype:

### Project Structure
```
my-fleet-prototype/
├── index.html
├── package.json
├── vite.config.js
├── data/
│   └── local.db              # (gitignored, shared separately)
├── raw_data/
│   └── fleet.csv             # (gitignored, shared separately)
├── analytics/                # ← Vite serves this (via publicDir config)
│   └── fleet_data.json
├── etl_to_sqlite.py          # One-time: raw → SQLite
├── generate_fleet_data.py    # SQLite → JSON
└── src/
    ├── App.jsx
    ├── App.module.css
    └── main.jsx
```

### package.json
```json
{
  "name": "my-fleet-prototype",
  "scripts": {
    "dev": "vite",
    "build": "vite build"
  },
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "recharts": "^2.10.0",
    "lucide-react": "^0.300.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.2.0",
    "vite": "^5.0.0"
  }
}
```

### vite.config.js
```javascript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  publicDir: 'analytics'  // Serve analytics/ as static files
});
```

### generate_fleet_data.py
```python
#!/usr/bin/env python3
"""Generate fleet analytics from SQLite database."""
import sqlite3
import json
from pathlib import Path

DB_PATH = "data/local.db"
OUTPUT = Path("analytics/fleet_data.json")

def main():
    conn = sqlite3.connect(DB_PATH)
    
    result = conn.execute("""
        SELECT unit_id, COUNT(*) as samples
        FROM telemetry
        GROUP BY unit_id
    """).fetchall()
    
    data = {
        "total_units": len(result),
        "units": [
            {"id": r[0], "samples": r[1], "status": "healthy"}
            for r in result
        ]
    }
    
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(data, indent=2))
    print(f"Wrote {OUTPUT}")

if __name__ == "__main__":
    main()
```

### src/App.jsx
```jsx
import { useState, useEffect } from 'react';
import { LayoutDashboard } from 'lucide-react';
import styles from './App.module.css';

function App() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/fleet_data.json')  // Served from analytics/
      .then(res => res.json())
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>Loading...</p>;

  return (
    <div className={styles.container}>
      <h1 className={styles.title}>
        <LayoutDashboard /> Fleet Dashboard
      </h1>
      <p>Total units: {data?.total_units}</p>
      <ul className={styles.list}>
        {data?.units?.map(u => (
          <li key={u.id}>{u.id} - {u.status}</li>
        ))}
      </ul>
    </div>
  );
}

export default App;
```

### src/App.module.css
```css
.container {
  max-width: 800px;
  margin: 0 auto;
  padding: 2rem;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

.title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #1e293b;
}

.list {
  list-style: none;
  padding: 0;
}

.list li {
  padding: 0.5rem;
  border-bottom: 1px solid #e2e8f0;
}
```

---

## 8. What Happens After You Push

Once your prototype is in git, Astrolabe will:

1. **Pull your repository** and review the structure
2. **Run your Python scripts** (using raw data or database you shared) to generate analytics
3. **Integrate React components** into `src/visualizers/{name}/`
4. **Upload analytics JSON** to S3 `datasets/{id}/analytics/`
5. **Convert raw data** to Parquet in S3 `datasets/{id}/data/`
6. **Test locally**, then deploy to production

**For large datasets:** Don't commit data files to git. Share them separately (Google Drive, S3, etc.) and document the download location in your README.

The closer your prototype follows this guide, the faster the integration.

---

## 9. Reference: Production Visualizer Structure

For context, here's how your prototype maps to the production structure:

```
data-visualization-tool/
├── src/
│   ├── visualizers/
│   │   ├── FluxPowerVisualizer.jsx     ← Entry, receives props from App.jsx
│   │   └── flux-power/                  ← Your components moved here
│   │       ├── FleetDashboard.jsx
│   │       ├── FleetDashboard.module.css
│   │       └── styles/
│   │           └── variables.css
│   └── services/
│       └── api.js                       ← Production API client
└── server/
    └── index.js                         ← Serves analytics from S3
```

In production, `fetch('/analytics/...')` becomes `api.getDatasetAnalytics(id, path)`.

---

*Last updated: January 2026*
