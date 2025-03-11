import streamlit as st
import pandas as pd
import google.generativeai as genai
import plotly.express as px
import requests
import re
import os
import pdfplumber
from colorthief import ColorThief

# 🔹 Load API key securely from Streamlit Secrets
API_KEY = st.secrets["GEMINI_API_KEY"]  # Ensure it's set in Streamlit Secrets

# 🔹 Configure Gemini AI
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro-latest")

# 🔹 Title
st.title("🐻📊 **BearViz - AI-Powered Data Visualization**")

# 🔹 File Upload
uploaded_file = st.file_uploader("Upload CSV, Excel, TXT, or PDF File", type=["csv", "xlsx", "txt", "pdf"])

# 🔹 API Data Fetching
api_url = st.text_input("Enter API URL for Live Data")

# 🔹 Image Upload for Color Extraction
uploaded_image = st.file_uploader("Upload an Image for Color Theme (Optional)", type=["png", "jpg", "jpeg"])

# 🔹 Extract Color Theme
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

    # **Read Different File Types**
    if file_name.endswith(".csv"):
        df = pd.read_csv(file_path)
    elif file_name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(file_path)
    elif file_name.endswith(".txt"):
        df = pd.read_csv(file_path, delimiter="\t", encoding="utf-8", error_bad_lines=False)
    elif file_name.endswith(".pdf"):
        with pdfplumber.open(file_path) as pdf:
            all_text = "\n".join([page.extract_text() for page in pdf.pages if page.extract_text()])
        df = pd.DataFrame({"Extracted_Text": all_text.split("\n")})  # Convert text into DataFrame

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

# 🔹 If Data is Loaded, Display & Analyze
if df is not None and not df.empty:
    st.write("### Dataset Preview")
    st.dataframe(df.head())

    # 🔹 Ask for Problem Statement
    problem_statement = st.text_input("What do you want to analyze?", "Example: Sales trend over time")

    if st.button("Generate Visualization"):
        st.write("📡 Sending request to Gemini AI...")

        # 🔹 Generate Visualization Using Gemini AI
        query = f"""
        Given this dataset summary:
        {df.describe().to_string()}

        The user wants to analyze: "{problem_statement}"

        The dataset file is: "{file_path}" (use this exact filename in the code)

        Generate a **Python script** that:
        - Loads the dataset using pandas
        - Uses **Plotly** to create an **interactive visualization**
        - Enables **hover tooltips** with dynamically relevant units (like currency, count, percentage)
        - Uses `plotly.express` and **returns a `fig` object instead of saving an image**
        - Uses the given color palette: {color_palette}
        - **Do NOT save the figure as an image**; just return `fig`
        - Do NOT assume a generic file name like 'dataset.csv'. Use "{file_path}" exactly.
        - Do NOT include explanations or Markdown formatting, only return runnable Python code.
        """

        try:
            response = model.generate_content(query)

            # 🔹 Ensure the response contains valid code
            if not response or not hasattr(response, "text") or not response.text.strip():
                st.error("❌ Gemini AI did not return valid Python code.")
                st.stop()

            generated_code = response.text.strip()

            # 🔹 Clean unwanted Markdown formatting
            generated_code = re.sub(r"^```python", "", generated_code, flags=re.MULTILINE)
            generated_code = re.sub(r"```$", "", generated_code, flags=re.MULTILINE)

            # 🔹 Print generated code for debugging
            print("\n🔹 Generated Python Code:\n", generated_code)

            # 🔹 Save the code safely
            script_path = "generated_visualization.py"
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(generated_code)

            # 🔹 Execute the script & retrieve the Plotly figure dynamically
            local_vars = {}
            exec(generated_code, globals(), local_vars)

            # 🔹 Extract `fig` from the executed script
            if "fig" in local_vars:
                st.plotly_chart(local_vars["fig"], use_container_width=True)
            else:
                st.error("❌ The generated code did not return a valid Plotly figure.")

        except Exception as e:
            st.error(f"❌ Error generating visualization: {e}")
