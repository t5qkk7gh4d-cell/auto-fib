Auto Fibonacci Tool — FastAPI + yfinance prototype
Quick start (local)
1.	Create a Python 3.11+ venv and activate it.
2.	Install dependencies:
pip install -r requirements.txt
3.	Run the app:
uvicorn main:app –host 0.0.0.0 –port 8000
4.	Open http://localhost:8000 in your browser. Type a ticker (e.g. AAPL) and click a timeframe button.
5.	The app will generate an image in output/ and display the chart + levels inline.
Deploy to Render (easy)
1.	In Render, create a new Web Service and connect this GitHub repo.
2.	Build Command: pip install -r requirements.txt
3.	Start Command: uvicorn main:app –host 0.0.0.0 –port $PORT
