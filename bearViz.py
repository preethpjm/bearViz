import streamlit as st
import pandas as pd
import google.generativeai as genai
import matplotlib.pyplot as plt
import seaborn as sns
import requests
import re
import os
from colorthief import ColorThief

# Load API key from Streamlit Secrets
API_KEY = st.secrets["GEMINI_API_KEY"]

# Configure Gemini
genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro-latest")

st.title("🐻📊 **BearViz**")

# File Upload
uploaded_file = st.file_uploader("Upload CSV or Excel File", type=["csv", "xlsx"])

# API Data Fetching
api_url = st.text_input("Enter API URL for Live Data")

# Image Upload
uploaded_image = st.file_uploader("Upload an Image for Color Theme (Optional)", type=["png", "jpg", "jpeg"])

# Extract Color Palette
def extract_colors(image):
    color_thief = ColorThief(image)
    palette = color_thief.get_palette(color_count=5)
    return ["#{:02x}{:02x}{:02x}".format(*color) for color in palette]

color_palette = ["#3498db", "#e74c3c", "#2ecc71", "#f1c40f", "#9b59b6"]
if uploaded_image:
    color_palette = extract_colors(uploaded_image)
    st.write("🎨 **Extracted Colors:**")
    # Create color swatch
    color_html = "".join(
        f"<div style='width: 40px; height: 40px; display: inline-block; margin: 5px; background-color: {color}; border-radius: 5px;'></div>"
        for color in color_palette
    )
    st.markdown(f"<div style='display: flex;'>{color_html}</div>", unsafe_allow_html=True)

# Load Data from File or API
df = None
file_name = None

if uploaded_file:
    file_name = uploaded_file.name
    file_path = os.path.join("data", file_name)
    os.makedirs("data", exist_ok=True)

    # Save file
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

# Display & Analyze Data
if df is not None and not df.empty:
    st.write("### Dataset Preview")
    st.dataframe(df.head())

    # Ask for Problem Statement
    problem_statement = st.text_input("What do you want to analyze?", "Example: Sales trend over time")

    if st.button("Generate Visualization"):
        st.write("📡📡📡 Sending request to Gemini AI...")

        # Generate Visualization
        query = f"""
        Given this dataset summary:
        {df.describe().to_string()}

        The user wants to analyze: "{problem_statement}"

        The dataset file is: "{file_path}" (use this exact filename in the code)

        Generate a Python script that:
        - Loads the dataset correctly using pandas
        - Uses Matplotlib/Seaborn to generate the best visualization
        - Applies the given color palette: {color_palette}
        - Saves the plot as 'visualization.png'
        - Do NOT assume a generic file name like 'dataset.csv'. Use "{file_path}" exactly.
        - Do NOT include explanations or Markdown formatting, only return runnable Python code.
        """

        try:
            response = model.generate_content(query)

            # Code Validation
            if not response or not hasattr(response, "text") or not response.text.strip():
                st.error("❌ Gemini AI did not return valid Python code.")
                st.stop()

            generated_code = response.text.strip()

            # Cleaning
            generated_code = re.sub(r"^```python", "", generated_code, flags=re.MULTILINE)
            generated_code = re.sub(r"```$", "", generated_code, flags=re.MULTILINE)

            print("\n🔹 Generated Python Code:\n", generated_code)

            # Save the code
            script_path = "generated_visualization.py"
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(generated_code)

            # Run the script
            try:
                exec(open(script_path).read(), globals())

                # Display the Visualization
                if os.path.exists("visualization.png"):
                    st.image("visualization.png", caption="Generated Visualization", use_container_width=True)
                else:
                    st.error("❌ The visualization was not generated successfully.")

            except Exception as e:
                st.error(f"❌ Error executing generated script: {e}")

        except Exception as e:
            st.error(f"❌ Error generating visualization: {e}")

