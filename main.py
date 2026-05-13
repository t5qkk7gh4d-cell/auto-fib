from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import yfinance as yf
import pandas as pd
import numpy as np
import os, time, hashlib
from scipy.signal import find_peaks
import plotly.graph_objects as go
from ta.volatility import AverageTrueRange
app = FastAPI()
if not os.path.exists(“output”):
os.makedirs(“output”)
app.mount(”/static”, StaticFiles(directory=“static”), name=“static”)
RANGE_MAP = {
“L24_hours”: (“2d”, “5m”),
“L7_days”: (“7d”, “15m”),
“L30_days”: (“1mo”, “1h”),
“L3_months”: (“3mo”, “4h”),
“L6_months”: (“6mo”, “1d”),
“L1_year”: (“1y”, “1d”),
“L3_years”: (“3y”, “1wk”),
“L5_years”: (“5y”, “1wk”),
“L_decade”: (“10y”, “1wk”),
}
FIB_RATIOS = [0.0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
@app.get(”/”, response_class=HTMLResponse)
async def homepage():
with open(“static/index.html”, “r”, encoding=“utf-8”) as f:
return HTMLResponse(f.read())
def fetch_ohlcv(ticker: str, period: str, interval: str) -> pd.DataFrame:
data = yf.download(tickers=ticker, period=period, interval=interval, progress=False, threads=False)
if data is None or data.empty:
raise ValueError(“No data returned for the requested ticker/interval.”)
data = data.dropna()
data.index = pd.to_datetime(data.index)
return data
def compute_atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
atr = AverageTrueRange(high=df[‘High’], low=df[‘Low’], close=df[‘Close’], window=length).average_true_range()
return atr.fillna(method=“bfill”)
def detect_structure_swing(df: pd.DataFrame, window: int = 5, atr_multiplier: float = 1.5):
highs = df[‘High’].values
lows = df[‘Low’].values
peaks, _ = find_peaks(highs, distance=window)
troughs, _ = find_peaks(-lows, distance=window)
if len(peaks) == 0 or len(troughs) == 0:
return None
atr = compute_atr(df)
extrema = []
for p in peaks:
extrema.append((“peak”, int(p), float(highs[p])))
for t in troughs:
extrema.append((“trough”, int(t), float(lows[t])))
extrema.sort(key=lambda x: x)[howtotrade]
for i in range(len(extrema)-1, 0, -1):
typ_i, idx_i, val_i = extrema[i-1]
typ_j, idx_j, val_j = extrema[i]
if typ_i == typ_j:
continue
mag = abs(val_j - val_i)
if idx_j > idx_i:
avg_atr = atr.iloc[max(0, idx_i):min(len(atr), idx_j+1)].mean()
else:
avg_atr = atr.iloc[max(0, idx_j):min(len(atr), idx_i+1)].mean()
if np.isnan(avg_atr):
avg_atr = atr.mean()
if mag >= atr_multiplier * avg_atr:
if typ_i == “trough” and typ_j == “peak”:
low_idx, high_idx = idx_i, idx_j
elif typ_i == “peak” and typ_j == “trough”:
low_idx, high_idx = idx_j, idx_i
else:
continue
low_price = lows[low_idx]
high_price = highs[high_idx]
return {“low_idx”: int(low_idx), “high_idx”: int(high_idx), “low_price”: float(low_price), “high_price”: float(high_price),
“low_ts”: str(df.index[low_idx]), “high_ts”: str(df.index[high_idx])}
return None
def fallback_minmax(df: pd.DataFrame):
low_pos = int(df[‘Low’].argmin())
high_pos = int(df[‘High’].argmax())
low_price = float(df[‘Low’].iloc[low_pos])
high_price = float(df[‘High’].iloc[high_pos])
return {“low_idx”: low_pos, “high_idx”: high_pos, “low_price”: low_price, “high_price”: high_price,
“low_ts”: str(df.index[low_pos]), “high_ts”: str(df.index[high_pos])}
def compute_fib_levels(low: float, high: float):
levels = []
diff = high - low
for r in FIB_RATIOS:
price = high - diff * r
levels.append({“ratio”: r, “price”: round(float(price), 6)})
return levels
def make_chart(df: pd.DataFrame, low_idx: int, high_idx: int, low_ts: str, high_ts: str, low_price: float, high_price: float, ticker: str):
fig = go.Figure(data=[go.Candlestick(x=df.index, open=df[‘Open’], high=df[‘High’], low=df[‘Low’], close=df[‘Close’], name=ticker)])
levels = compute_fib_levels(low_price, high_price)
for lvl in levels:
fig.add_hline(y=lvl[“price”], line=dict(color=“rgba(0,0,0,0.6)”), annotation_text=f’{int(lvl[“ratio”]*1000)/10}% {lvl[“price”]}’, annotation_position=“left”)
pocket_low = next(l for l in levels if l[“ratio”] == 0.382)[“price”]
pocket_high = next(l for l in levels if l[“ratio”] == 0.618)[“price”]
fig.add_hrect(y0=pocket_low, y1=pocket_high, fillcolor=“gold”, opacity=0.15, line_width=0)
fig.add_scatter(x=[pd.to_datetime(low_ts)], y=[low_price], mode=“markers+text”, marker=dict(color=“blue”, size=8), text=[“Swing Low”], textposition=“bottom right”)
fig.add_scatter(x=[pd.to_datetime(high_ts)], y=[high_price], mode=“markers+text”, marker=dict(color=“red”, size=8), text=[“Swing High”], textposition=“top right”)
fig.update_layout(margin=dict(l=40, r=40, t=40, b=40), showlegend=False, template=“plotly_white”)
key = f”{ticker}_{int(time.time())}”
filename = os.path.join(“output”, f”{hashlib.md5(key.encode()).hexdigest()}.png”)
fig.write_image(filename, width=1200, height=700, scale=1)
return filename, levels
@app.get(”/api/fib”)
async def api_fib(ticker: str, range: str):
ticker = ticker.upper().strip()
if range not in RANGE_MAP:
raise HTTPException(status_code=400, detail=“Invalid range”)
period, interval = RANGE_MAP[range]
try:
df = fetch_ohlcv(ticker, period=period, interval=interval)
except Exception as e:
raise HTTPException(status_code=500, detail=f”Data fetch error: {e}”)
if df.shape < 10:
try:
df = fetch_ohlcv(ticker, period=“1y”, interval=“1d”)
except Exception as e:
raise HTTPException(status_code=500, detail=f”No usable data for ticker {ticker}.”)
try:
struct = detect_structure_swing(df)
except Exception:
struct = None
if struct is None:
fb = fallback_minmax(df)
low_price, high_price = fb[“low_price”], fb[“high_price”]
low_ts, high_ts = fb[“low_ts”], fb[“high_ts”]
low_idx, high_idx = fb[“low_idx”], fb[“high_idx”]
else:
low_price, high_price = struct[“low_price”], struct[“high_price”]
low_ts, high_ts = struct[“low_ts”], struct[“high_ts”]
low_idx, high_idx = struct[“low_idx”], struct[“high_idx”]
if abs(high_price - low_price) < 1e-6 or high_price == 0:
fb = fallback_minmax(df)
low_price, high_price = fb[“low_price”], fb[“high_price”]
low_ts, high_ts = fb[“low_ts”], fb[“high_ts”]
low_idx, high_idx = fb[“low_idx”], fb[“high_idx”]
png_path, levels = make_chart(df, low_idx, high_idx, low_ts, high_ts, low_price, high_price, ticker)
image_url = f”/image/{os.path.basename(png_path)}”
payload = {
“ticker”: ticker,
“range”: range,
“endpoints”: {“low”: {“ts”: low_ts, “price”: low_price}, “high”: {“ts”: high_ts, “price”: high_price}},
“levels”: levels,
“image”: image_url
}
return JSONResponse(payload)
@app.get(”/image/{fname}”)
async def image(fname: str):
path = os.path.join(“output”, fname)
if not os.path.exists(path):
raise HTTPException(status_code=404, detail=“Image not found”)
return FileResponse(path, media_type=“image/png”)
