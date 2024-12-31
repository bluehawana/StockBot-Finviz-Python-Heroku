from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
import plotly.graph_objects as go
from fpdf import FPDF
import os
from dotenv import load_dotenv
import pandas as pd
import requests
import yfinance as yf
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz
from mailjet_rest import Client
import base64
import logging

load_dotenv()

app = FastAPI(
    title="Stock Screener API",
    description="API for generating stock analysis reports based on Finviz screener",
    version="1.0.0"
)
scheduler = AsyncIOScheduler()

# Finviz API Configuration
FINVIZ_API_KEY = os.getenv("RAPIDAPI_KEY")
FINVIZ_HOST = "finviz-screener.p.rapidapi.com"

# Email configuration
mailjet = Client(auth=(os.getenv('MAILJET_API_KEY'), os.getenv('MAILJET_API_SECRET')), version='v3.1')

# Add this import for debugging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)

async def get_screened_stocks():
    """Get stocks based on Finviz screener criteria"""
    url = "https://finviz-screener.p.rapidapi.com/table"  # Changed back to /table endpoint
    
    headers = {
        "X-RapidAPI-Key": FINVIZ_API_KEY,
        "X-RapidAPI-Host": FINVIZ_HOST
    }
    
    # Updated params to match the working example
    params = {
        "order": "change",
        "desc": "true",
        "filters": ["cap_small", "sh_relvol_o3", "ta_perf_dup"]
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        
        # Log raw response for debugging
        print('Raw API Response:', response.text)
        
        if not response.ok:
            raise Exception(f"API response: {response.status_code} {response.reason}")
            
        data = response.json()
        
        # Get top 19 stocks from the response
        stocks = []
        if isinstance(data, dict) and 'rows' in data:
            stocks = data['rows'][:19]
        
        if not stocks:
            raise ValueError("No stocks found matching the criteria")
            
        # Transform the data to match our needs
        transformed_stocks = []
        for stock in stocks:
            transformed_stocks.append({
                'ticker': stock[1],  # Symbol is typically in second column
                'change': stock[9],  # Change % is typically in 10th column
                'market_cap': stock[6],
                'volume': stock[7],
                'relative_volume': stock[8]
            })
            
        return transformed_stocks
        
    except requests.RequestException as e:
        raise Exception(f"Failed to fetch data from Finviz API: {str(e)}")
    except ValueError as e:
        raise Exception(str(e))
    except Exception as e:
        raise Exception(f"Unexpected error while fetching stocks: {str(e)}")

async def create_finviz_style_chart(symbol):
    """Create a chart similar to Finviz style using intraday data"""
    try:
        logging.info(f"Starting chart generation for {symbol}")
        data = yf.download(symbol, period="5d", interval="1h", progress=False)
        logging.info(f"Downloaded data for {symbol}: {len(data)} rows")
        
        if data.empty:
            logging.error(f"No data received for {symbol}")
            fig = go.Figure()
            fig.add_annotation(
                text="No data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False
            )
            logging.info("Created empty chart with 'No data available' message")
        else:
            logging.info(f"Creating chart for {symbol} with {len(data)} data points")
            # Create Plotly figure
            fig = go.Figure()
            
            # Add candlestick chart
            fig.add_trace(go.Candlestick(
                x=data.index,
                open=data['Open'],
                high=data['High'],
                low=data['Low'],
                close=data['Close'],
                name='Price'
            ))
            
            # Add volume bar chart
            fig.add_trace(go.Bar(
                x=data.index,
                y=data['Volume'],
                name='Volume',
                yaxis='y2',
                marker_color='rgba(128,128,128,0.5)'
            ))
        
        # Style the chart
        fig.update_layout(
            title=f"{symbol} Price Chart",
            yaxis_title="Price ($)",
            yaxis2=dict(
                title="Volume",
                overlaying="y",
                side="right",
                showgrid=False
            ),
            xaxis_title="Date",
            template="plotly_white",
            xaxis_rangeslider_visible=False,
            plot_bgcolor='rgb(255,255,255)',
            paper_bgcolor='rgb(255,255,255)',
            height=400,
            width=800,
            showlegend=False,
            margin=dict(l=50, r=50, t=50, b=50)
        )
        
        # Save chart as image with higher DPI
        img_path = f"temp_{symbol}.png"
        logging.info(f"Attempting to save chart to {img_path}")
        fig.write_image(img_path, scale=2)
        
        file_size = os.path.getsize(img_path) if os.path.exists(img_path) else 0
        logging.info(f"Chart file created: {img_path} (size: {file_size} bytes)")
        
        # Verify the file exists and has content
        if not os.path.exists(img_path) or os.path.getsize(img_path) == 0:
            raise ValueError(f"Failed to create chart image for {symbol}")
            
        return img_path
        
    except Exception as e:
        logging.error(f"Error in chart generation for {symbol}: {str(e)}", exc_info=True)
        raise

async def generate_stock_report(stocks):
    logging.info(f"Generating report for {len(stocks)} stocks")
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    successful_charts = 0
    
    for stock in stocks:
        try:
            symbol = stock.get('ticker', '')
            change = stock.get('change', '0')
            
            logging.info(f"Processing stock: {symbol}")
            
            if not symbol:
                logging.warning("Empty symbol found, skipping")
                continue
            
            # Add to PDF first (so we at least get the text)
            pdf.add_page()
            pdf.set_font('Arial', 'B', 16)
            pdf.cell(0, 10, f"{symbol} Analysis", ln=True, align='C')
            pdf.set_font('Arial', '', 12)
            pdf.cell(0, 10, f"Daily Change: {change}", ln=True, align='C')
            
            try:
                # Generate chart
                chart_path = await create_finviz_style_chart(symbol)
                logging.info(f"Chart generated: {chart_path}")
                
                # Add chart to PDF if it exists
                if os.path.exists(chart_path):
                    logging.info(f"Adding chart to PDF: {chart_path}")
                    pdf.image(chart_path, x=10, y=30, w=190)
                    successful_charts += 1
                    os.remove(chart_path)  # Clean up
            except Exception as chart_error:
                logging.error(f"Chart generation failed for {symbol}: {str(chart_error)}")
                pdf.cell(0, 10, "Chart generation failed", ln=True, align='C')
            
            # Add metrics (even if chart fails)
            pdf.set_y(200)
            pdf.cell(0, 10, f"Market Cap: {stock.get('market_cap', 'N/A')}", ln=True)
            pdf.cell(0, 10, f"Volume: {stock.get('volume', 'N/A')}", ln=True)
            pdf.cell(0, 10, f"Relative Volume: {stock.get('relative_volume', 'N/A')}", ln=True)
            
        except Exception as e:
            logging.error(f"Error processing {symbol}: {str(e)}")
            continue
    
    # Add summary page
    pdf.add_page()
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, "Report Summary", ln=True, align='C')
    pdf.set_font('Arial', '', 12)
    pdf.cell(0, 10, f"Total stocks processed: {len(stocks)}", ln=True)
    pdf.cell(0, 10, f"Successful charts generated: {successful_charts}", ln=True)
    
    pdf_path = "stock_analysis.pdf"
    logging.info(f"Saving PDF to {pdf_path}")
    pdf.output(pdf_path)
    
    # Verify PDF was created
    if not os.path.exists(pdf_path) or os.path.getsize(pdf_path) == 0:
        raise ValueError("Failed to create PDF or PDF is empty")
    
    logging.info(f"PDF generated successfully with {successful_charts} charts")
    return pdf_path

async def send_email_report(pdf_path):
    """Separate function to handle email sending with better error handling"""
    try:
        logging.info("Starting email sending process")
        
        # Read and encode PDF
        logging.info(f"Reading PDF file: {pdf_path}")
        with open(pdf_path, 'rb') as pdf_file:
            encoded_pdf = base64.b64encode(pdf_file.read()).decode('utf-8')
        
        logging.info("PDF encoded successfully")
        
        # Prepare email data
        recipient_email = os.getenv("PERSONAL_EMAIL")
        sender_email = os.getenv("MAIL_FROM")
        
        logging.info(f"Preparing email from {sender_email} to {recipient_email}")
        
        data = {
            'Messages': [
                {
                    "From": {
                        "Email": sender_email,
                        "Name": "Stock Analysis"
                    },
                    "To": [
                        {
                            "Email": recipient_email,
                            "Name": "Recipient"
                        }
                    ],
                    "Subject": f"Stock Analysis Report {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                    "TextPart": "Please find attached today's stock analysis report.",
                    "HTMLPart": "<h3>Stock Analysis Report</h3><p>Please find attached today's stock analysis report.</p>",
                    "Attachments": [
                        {
                            "ContentType": "application/pdf",
                            "Filename": "stock_analysis.pdf",
                            "Base64Content": encoded_pdf
                        }
                    ]
                }
            ]
        }
        
        logging.info("Sending email via Mailjet")
        result = mailjet.send.create(data=data)
        
        logging.info(f"Mailjet API response status code: {result.status_code}")
        response_json = result.json()
        logging.info(f"Mailjet API response: {response_json}")
        
        if result.status_code != 200:
            raise Exception(f"Failed to send email. Mailjet response: {response_json}")
            
        logging.info("Email sent successfully")
        return True
        
    except Exception as e:
        logging.error(f"Error sending email: {str(e)}", exc_info=True)
        raise

async def daily_task():
    """Daily task to generate and send report"""
    try:
        logging.info("Starting daily task")
        stocks = await get_screened_stocks()
        logging.info(f"Retrieved {len(stocks)} stocks")
        
        pdf_path = await generate_stock_report(stocks)
        logging.info(f"Generated PDF report: {pdf_path}")
        
        # Send email
        await send_email_report(pdf_path)
        
        # Clean up PDF file
        os.remove(pdf_path)
        logging.info("Daily task completed successfully")
        
    except Exception as e:
        logging.error(f"Error in daily task: {str(e)}", exc_info=True)
        raise

@app.on_event("startup")
async def start_scheduler():
    """Start the scheduler when the app starts"""
    scheduler.add_job(
        daily_task,
        'cron',
        hour=15,
        minute=30,
        timezone=pytz.timezone('Europe/Stockholm'),
        day_of_week='mon-fri'
    )
    scheduler.start()

@app.get("/generate-report")
async def generate_report(background_tasks: BackgroundTasks):
    """Generate and send stock analysis report"""
    try:
        await daily_task()
        return JSONResponse(
            status_code=200,
            content={
                "message": "Stock analysis report generated and sent successfully",
                "recipient": os.getenv("PERSONAL_EMAIL")
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate report: {str(e)}"
        )

@app.get("/")
async def root():
    return {
        "message": "Welcome to Stock Screener API",
        "endpoints": {
            "generate_report": "/generate-report",
            "docs": "/docs",
            "openapi": "/openapi.json"
        }
    }

@app.get("/test-finviz")
async def test_finviz_connection():
    """Test the Finviz API connection"""
    try:
        url = "https://finviz-screener.p.rapidapi.com/table"
        headers = {
            "X-RapidAPI-Key": FINVIZ_API_KEY,
            "X-RapidAPI-Host": FINVIZ_HOST
        }
        params = {
            "order": "change",
            "desc": "true",
            "filters": ["cap_small", "sh_relvol_o3", "ta_perf_dup"]
        }
        
        response = requests.get(url, headers=headers, params=params)
        
        return {
            "status": "success",
            "status_code": response.status_code,
            "raw_response": response.text,  # Include raw response for debugging
            "response": response.json() if response.ok else None
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to connect to Finviz API: {str(e)}"
        ) 

@app.get("/test-chart/{symbol}")
async def test_chart(symbol: str):
    """Test endpoint to generate a single chart"""
    try:
        chart_path = await create_finviz_style_chart(symbol)
        return {"status": "success", "chart_path": chart_path}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate chart: {str(e)}"
        ) 

@app.get("/test-stocks")
async def test_stocks():
    """Test endpoint to get stock data without generating charts"""
    try:
        stocks = await get_screened_stocks()
        return {
            "status": "success",
            "count": len(stocks),
            "stocks": stocks
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get stocks: {str(e)}"
        ) 

@app.get("/test-single/{symbol}")
async def test_single(symbol: str):
    """Test endpoint to generate a report for a single stock"""
    try:
        stock_data = {
            'ticker': symbol,
            'change': '0%',
            'market_cap': 'N/A',
            'volume': 'N/A',
            'relative_volume': 'N/A'
        }
        pdf_path = await generate_stock_report([stock_data])
        return {"status": "success", "pdf_path": pdf_path}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate report: {str(e)}"
        ) 

@app.get("/debug-chart/{symbol}")
async def debug_chart(symbol: str):
    """Debug endpoint for chart generation"""
    try:
        logging.info(f"Debug: Starting chart generation for {symbol}")
        
        # Download data
        data = yf.download(symbol, period="5d", interval="1h", progress=False)
        logging.info(f"Debug: Downloaded {len(data)} rows of data")
        
        # Create simple line chart
        fig = go.Figure(data=go.Scatter(x=data.index, y=data['Close']))
        
        # Save to file
        img_path = f"debug_{symbol}.png"
        fig.write_image(img_path)
        
        file_exists = os.path.exists(img_path)
        file_size = os.path.getsize(img_path) if file_exists else 0
        
        return {
            "status": "success",
            "data_points": len(data),
            "file_exists": file_exists,
            "file_size": file_size,
            "file_path": img_path
        }
    except Exception as e:
        logging.error(f"Debug: Error in chart generation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=str(e)
        ) 

@app.get("/test-email")
async def test_email():
    """Test endpoint for email functionality"""
    try:
        # Create a simple test PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, "Test Email PDF", ln=True, align='C')
        pdf.cell(0, 10, f"Generated at: {datetime.now()}", ln=True, align='C')
        
        test_pdf_path = "test_email.pdf"
        pdf.output(test_pdf_path)
        
        # Send test email
        await send_email_report(test_pdf_path)
        
        # Clean up
        os.remove(test_pdf_path)
        
        return {
            "status": "success",
            "message": f"Test email sent to {os.getenv('PERSONAL_EMAIL')}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send test email: {str(e)}"
        ) 

@app.get("/check-env")
async def check_env():
    """Check email-related environment variables"""
    return {
        "MAILJET_API_KEY": bool(os.getenv("MAILJET_API_KEY")),
        "MAILJET_API_SECRET": bool(os.getenv("MAILJET_API_SECRET")),
        "MAIL_FROM": os.getenv("MAIL_FROM"),
        "PERSONAL_EMAIL": os.getenv("PERSONAL_EMAIL")
    } 