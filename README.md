# StockBot-Finviz-Python-Heroku

# 📈 Automatic Stock Bot

This is an **Automatic Stock Bot** that monitors the **top 20 stocks** in the American stock market based on:
- **Trading volume**
- **Daily performance**
- **Other financial indices**

The bot automatically sends email updates with the results, including performance charts and key metrics. It uses **FastAPI Finviz** for data collection and processing.

---

## 🚀 Features
- Tracks the **top-performing stocks** with high trading activity.
- Sends email updates **automatically** to keep you informed.
- Provides **visualized charts** (coming soon) for easier analysis.
- Fully hosted and automated — just set it up once!

---

## 🔧 Technologies Used
- **Cloudflare Workers** for serverless automation.
- **SendGrid** for sending automated email updates.
- **RapidAPI Finviz API** for stock data.

---

## 📬 How It Works
1. The bot fetches data from the **Finviz API** using filters such as market cap, trading volume, and performance.
2. It processes and ranks the top 20 stocks.
3. Emails with data and charts are sent to subscribers.

---

### ☕ Support My Work
If you enjoy this project and want to see more features added, consider supporting me by buying me a coffee! Your support helps cover hosting fees and future improvements.

[![Buy Me a Coffee](https://img.buymeacoffee.com/button-api/?text=Buy%20me%20a%20coffee&emoji=&slug=your-username&button_colour=FF5F5F&font_colour=ffffff&font_family=Arial&outline_colour=000000&coffee_colour=FFDD00)](https://www.buymeacoffee.com/bluehawana)

---

## 🛠️ How to Use
1. Clone the repository:
   ```bash
   git clone https://github.com/your-username/automatic-stock-bot.git

2. **Set up environment variables:**
   - Create a `.env` file in your project's root directory to store your API keys.
   - Example `.env` file content:
     ```bash
     RAPIDAPI_KEY=your_finviz_api_key_here
     SENDGRID_API_KEY=your_sendgrid_api_key_here
     ```

3. **Install Dependencies:**
   - Navigate to your project directory and install the required dependencies:
     ```bash
     cd automatic-stock-bot
     npm install
     ```

4. **Start the Development Server:**
   - Run the server in development mode:
     ```bash
     npm run dev
     ```
   - This will start the worker on localhost (default: http://localhost:8787).

5. **Deploy the Worker:**
   - Deploy the project to Cloudflare Workers:
     ```bash
     npm run deploy
     ```
   - Your worker will now be live. Make sure to update the environment variables in Cloudflare Workers with the `RAPIDAPI_KEY` and `SENDGRID_API_KEY`.
