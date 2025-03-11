import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px
import requests
import re
import os
from colorthief import ColorThief
import subprocess

# 🔹 Load API key securely from Streamlit Secrets
API_KEY = st.secrets["GEMINI_API_KEY"]

# 🔹 Configure Gemini AI
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro-latest")

st.title("🐻📊 **BearViz - AI-Powered Dashboard**")

# 🔹 File Upload
uploaded_file = st.file_uploader("Upload CSV or Excel File", type=["csv", "xlsx"])

# 🔹 API Data Fetching
api_url = st.text_input("Enter API URL for Live Data")

# 🔹 Image Upload for Color Extraction
uploaded_image = st.file_uploader("Upload an Image for Color Theme (Optional)", type=["png", "jpg", "jpeg"])

# 🔹 Extract Color Palette
def extract_colors(image):
    color_thief = ColorThief(image)
    palette = color_thief.get_palette(color_count=5)
    return ["#{:02x}{:02x}{:02x}".format(*color) for color in palette]

color_palette = ["#3498db", "#e74c3c", "#2ecc71", "#f1c40f", "#9b59b6"]
if uploaded_image:
    color_palette = extract_colors(uploaded_image)
    st.write("🎨 **Extracted Colors:**")
    color_html = "".join(
        f"<div style='width: 40px; height: 40px; display: inline-block; margin: 5px; background-color: {color}; border-radius: 5px;'></div>"
        for color in color_palette
    )
    st.markdown(f"<div style='display: flex;'>{color_html}</div>", unsafe_allow_html=True)

# 🔹 Load Data from File or API
df = None
file_name = None

if uploaded_file:
    file_name = uploaded_file.name
    file_path = os.path.join("data", file_name)
    os.makedirs("data", exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    df = pd.read_csv(file_path) if file_name.endswith(".csv") else pd.read_excel(file_path)

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

# 🔹 Generate Dashboard if Data is Loaded
if df is not None and not df.empty:
    st.write("### Dataset Preview")
    st.dataframe(df.head())

    # 🔹 Accept multiple problem statements for dashboard
    st.write("📝 **Enter Your Analysis Questions** (One per line)")
    problem_statements = st.text_area("Example: Sales vs Region, Region vs Sale Category").split("\n")

    if st.button("Generate Dashboard"):
        st.write("📡 Generating multiple visualizations...")

        col1, col2 = st.columns(2)  # Two-column layout for dashboard
        for i, problem in enumerate(problem_statements):
            problem = problem.strip()
            if not problem:
                continue

            st.subheader(f"📊 {problem}")

            query = f"""
            Given this dataset summary:
            {df.describe().to_string()}

            The user wants to analyze: "{problem}"

            Generate a Python script that:
            - Loads the dataset correctly using pandas
            - Uses Plotly to create an interactive visualization
            - Saves the plot as 'visualization_{i}.png' OR renders directly in Streamlit
            - Do NOT assume specific column names; infer them dynamically
            - Avoid Markdown formatting, only return raw Python code.
            """

            try:
                response = model.generate_content(query)

                if not response or not hasattr(response, "text") or not response.text.strip():
                    st.error(f"❌ No valid code returned for '{problem}'")
                    continue

                generated_code = response.text.strip()

                # 🔹 Clean the code from Markdown artifacts
                generated_code = re.sub(r"^```python", "", generated_code, flags=re.MULTILINE)
                generated_code = re.sub(r"```$", "", generated_code, flags=re.MULTILINE)

                script_path = f"generated_{problem.replace(' ', '_')}.py"
                with open(script_path, "w", encoding="utf-8") as f:
                    f.write(generated_code)

                # 🔹 Run each script as a separate process
                try:
                    subprocess.run(["python", script_path], check=True)

                    # 🔹 Display the generated visualization
                    image_path = f"visualization_{i}.png"
                    if os.path.exists(image_path):
                        with (col1 if i % 2 == 0 else col2):  # Alternate columns
                            st.image(image_path, caption=problem, use_container_width=True)
                    else:
                        st.error(f"❌ Visualization failed for '{problem}'")

                except Exception as e:
                    st.error(f"❌ Error executing script for '{problem}': {e}")

            except Exception as e:
                st.error(f"❌ Error generating visualization: {e}")

