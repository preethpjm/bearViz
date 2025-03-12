import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px
import requests
import re
import os
import pdfplumber
import random
from colorthief import ColorThief

# Load API Key securely
API_KEY = st.secrets["GEMINI_API_KEY"]
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro-latest")

# Set Page Configuration
st.set_page_config(page_title="BearViz - AI Dashboard", layout="wide")

# Sidebar Navigation
with st.sidebar:
    st.image("bearviz_logo.png", width=100)  # Replace with actual logo
    menu_option = st.radio("Navigation", ["📂 Upload Data", "🎨 Color Palette", "📊 AI Dashboard"])

# File Upload Section
if menu_option == "📂 Upload Data":
    st.title("📂 Upload Dataset")
    uploaded_file = st.file_uploader("Upload CSV, Excel, TXT, or PDF File", type=["csv", "xlsx", "txt", "pdf"])
    api_url = st.text_input("Enter API URL for Live Data")

    df = None
    if uploaded_file:
        file_name = uploaded_file.name
        file_path = os.path.join("data", file_name)
        os.makedirs("data", exist_ok=True)

        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())

        if file_name.endswith(".csv"):
            df = pd.read_csv(file_path)
        elif file_name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(file_path)
        elif file_name.endswith(".txt"):
            df = pd.read_csv(file_path, delimiter="\t", encoding="utf-8", on_bad_lines="skip")
        elif file_name.endswith(".pdf"):
            with pdfplumber.open(file_path) as pdf:
                all_text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
            df = pd.DataFrame({"Extracted_Text": all_text.split("\n")})

    elif api_url:
        try:
            response = requests.get(api_url)
            response.raise_for_status()
            df = pd.DataFrame(response.json())
            file_name = "live_data.csv"
            file_path = os.path.join("data", file_name)
            df.to_csv(file_path, index=False)
        except Exception as e:
            st.error(f"❌ API Fetch Failed: {e}")

    if df is not None:
        st.write("### Dataset Preview")
        st.dataframe(df.head())
        st.session_state["df"] = df  # Store dataset in session state

# Color Palette Section
elif menu_option == "🎨 Color Palette":
    st.title("🎨 Choose Color Palette")
    uploaded_image = st.file_uploader("Upload an Image for Color Theme", type=["png", "jpg", "jpeg"])

    def extract_colors(image, required_colors):
        color_thief = ColorThief(image)
        extracted_colors = color_thief.get_palette(color_count=min(required_colors, 10))
        extracted_hex = ["#{:02x}{:02x}{:02x}".format(*color) for color in extracted_colors]

        while len(extracted_hex) < required_colors:
            base_color = extracted_hex[len(extracted_hex) % len(extracted_hex)]
            new_color = "#{:02x}{:02x}{:02x}".format(
                (int(base_color[1:3], 16) + random.randint(20, 50)) % 256,
                (int(base_color[3:5], 16) + random.randint(20, 50)) % 256,
                (int(base_color[5:7], 16) + random.randint(20, 50)) % 256
            )
            extracted_hex.append(new_color)

        return extracted_hex[:required_colors]

    color_palette = st.session_state.get("color_palette", ["#3498db", "#e74c3c", "#2ecc71", "#f1c40f", "#9b59b6"])
    if uploaded_image:
        required_colors = 8
        color_palette = extract_colors(uploaded_image, required_colors)
        st.session_state["color_palette"] = color_palette

    st.write("🎨 **Extracted Colors:**")
    color_html = "".join(
        f"<div style='width: 40px; height: 40px; display: inline-block; margin: 5px; background-color: {color}; border-radius: 5px;'></div>"
        for color in color_palette
    )
    st.markdown(f"<div style='display: flex;'>{color_html}</div>", unsafe_allow_html=True)

# AI Dashboard Section
elif menu_option == "📊 AI Dashboard":
    st.title("📊 AI-Powered Dashboard")

    if "df" not in st.session_state:
        st.warning("⚠️ Please upload a dataset first!")
        st.stop()

    df = st.session_state["df"]
    st.write("### Dataset Overview")
    st.dataframe(df.head())

    problem_statement = st.text_input("Enter Analysis Request", "Example: Sales trend over time")
    if st.button("Generate Visualization"):
        st.write("📡 Requesting Gemini AI...")

        query = f"""
        Given this dataset summary:
        {df.describe().to_string()}

        The user wants to analyze: "{problem_statement}"
        The dataset file is: "{file_name}"
        Generate a **Python script** that:
        - Loads the dataset using pandas
        - Uses **Plotly** to create an **interactive visualization**
        - Enables **hover tooltips** with dynamically relevant units
        - Uses `plotly.express` and **returns a `fig` object instead of saving an image**
        - Uses the given color palette: {color_palette}
        - Do NOT include explanations or Markdown formatting, only return runnable Python code.
        """

        try:
            response = model.generate_content(query)
            if not response or not hasattr(response, "text") or not response.text.strip():
                st.error("❌ Gemini AI did not return valid Python code.")
                st.stop()

            generated_code = response.text.strip()
            generated_code = re.sub(r"^```python", "", generated_code, flags=re.MULTILINE)
            generated_code = re.sub(r"```$", "", generated_code, flags=re.MULTILINE)

            script_path = "generated_visualization.py"
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(generated_code)

            local_vars = {}
            exec(generated_code, globals(), local_vars)

            if "fig" in local_vars:
                st.plotly_chart(local_vars["fig"], use_container_width=True)
            else:
                st.error("❌ AI did not return a valid Plotly figure.")

        except Exception as e:
            st.error(f"❌ Error generating visualization: {e}")
