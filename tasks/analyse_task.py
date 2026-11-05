from crewai import Task
from agents.analyst_agent import analyst_agent

get_stock_analysis = Task(
    description=(
        "Analyze the stock: {stock} focusing on the INDIAN STOCK MARKET context.\n"
        "Use the provided context heavily to understand whether the stock should be invested in:\n"
        "- Fundamental Metrics: {fundamentals_context}\n"
        "- Recent News/Announcements: {news_context}\n"
        "- Corporate Actions: {actions_context}\n"
        "- Technical Patterns: {patterns_context}\n"
        "- Technical Indicators: {technical_indicators_context}\n\n"
        "Your core objective is to synthesize this data into a specific highly-structured report."
    ),
    expected_output=(
        "You MUST format your EXACT response strictly using these three headings:\n\n"
        "### 📊 Technical Analysis\n"
        "[Provide exactly 4-5 sentences analyzing the technical indicators, chart patterns, and recent price/volume action.]\n\n"
        "### 🏢 Fundamental Analysis\n"
        "[Provide exactly 4-5 sentences analyzing the fundamental health (P/E, Market Cap, Debt etc), corporate actions, and recent news impacts. State clearly if fundamentally the stock is investable.]\n\n"
        "### 💡 Actionable Summary\n"
        "[Provide exactly 3-4 sentences synthesizing the final verdict (Buy/Sell/Hold) with clear risk/reward logic.]\n\n"
        "Do NOT output anything else except these three headings with their corresponding paragraphs."
    ),
    agent=analyst_agent
)