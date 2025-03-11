import streamlit as st
import pandas as pd
import google.generativeai as genai
import matplotlib.pyplot as plt
import seaborn as sns
import requests
import re
import os
from colorthief import ColorThief

# 🔹 Configure Gemini AI
genai.configure(api_key="AIzaSyBY_NygxPdVVWfTp5wH_cuhdUp26H7WqTg")  # Replace with your actual API key
model = genai.GenerativeModel("gemini-1.5-pro-latest")

st.title("📊 AI-Powered Data Visualization")

# 🔹 File Upload
uploaded_file = st.file_uploader("Upload CSV or Excel File", type=["csv", "xlsx"])

# 🔹 API Data Fetching
api_url = st.text_input("Enter API URL for Live Data")

# 🔹 Image Upload for Color Extraction
uploaded_image = st.file_uploader("Upload an Image for Color Theme (Optional)", type=["png", "jpg", "jpeg"])

# 🔹 Extract Color Theme
def extract_colors(image):
    color_thief = ColorThief(image)
    palette = color_thief.get_palette(color_count=5)
    return ["#{:02x}{:02x}{:02x}".format(*color) for color in palette]

color_palette = ["#3498db", "#e74c3c", "#2ecc71", "#f1c40f", "#9b59b6"]  # Default Colors
if uploaded_image:
    color_palette = extract_colors(uploaded_image)
    st.write("🎨 Extracted Colors:", color_palette)

# 🔹 Load Data from File or API
df = None
file_name = None

if uploaded_file:
    file_name = uploaded_file.name
    df = pd.read_csv(uploaded_file) if file_name.endswith(".csv") else pd.read_excel(uploaded_file)
elif api_url:
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        df = pd.DataFrame(response.json())
        file_name = "live_data.csv"
    except Exception as e:
        st.error(f"❌ API Fetch Failed: {e}")

# 🔹 If Data is Loaded, Display & Analyze
if df is not None and not df.empty:
    st.write("### Dataset Preview")
    st.dataframe(df.head())

    # 🔹 Ask for Problem Statement
    problem_statement = st.text_input("What do you want to analyze?", "Example: Sales trend over time")

    if st.button("Generate Visualization"):
        st.write("🔄 Generating visualization using Gemini AI...")

        # 🔹 Generate Visualization Using Gemini AI
        query = f"""
        Given this dataset summary:
        {df.describe().to_string()}
        
        The user wants to analyze: "{problem_statement}"
        
        Generate a Python script that:
        - Loads the dataset using pandas
        - Uses Matplotlib/Seaborn to generate the best visualization
        - Applies the given color palette: {color_palette}
        - Saves the plot as 'visualization.png'
        - Do NOT include explanations or Markdown formatting, only return runnable Python code.
        """

        try:
            response = model.generate_content(query)
            
            # 🔹 Ensure the response contains valid code
            if not response or not hasattr(response, "text") or not response.text.strip():
                st.error("❌ Gemini AI did not return valid Python code.")
            else:
                generated_code = response.text.strip()

                # 🔹 Clean unwanted Markdown formatting
                generated_code = re.sub(r"^```python", "", generated_code, flags=re.MULTILINE)
                generated_code = re.sub(r"```$", "", generated_code, flags=re.MULTILINE)

                # 🔹 Save the code safely
                script_path = "generated_visualization.py"
                with open(script_path, "w", encoding="utf-8") as f:
                    f.write(generated_code)

                # 🔹 Run the script safely
                try:
                    exec(open(script_path).read(), globals())

                    # 🔹 Display the Visualization
                    if os.path.exists("visualization.png"):
                        st.image("visualization.png", caption="Generated Visualization", use_column_width=True)
                    else:
                        st.error("❌ The visualization was not generated successfully.")

                except Exception as e:
                    st.error(f"❌ Error executing generated script: {e}")

        except Exception as e:
            st.error(f"❌ Error generating visualization: {e}")
