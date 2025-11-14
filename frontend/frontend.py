import streamlit as st
import requests

# Page config with custom theme
st.set_page_config(
    page_title="Pack & Go",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Initialize session state
if "itinerary_generated" not in st.session_state:
    st.session_state.itinerary_generated = False
if "current_itinerary" not in st.session_state:
    st.session_state.current_itinerary = None
if "structured_itinerary" not in st.session_state:
    st.session_state.structured_itinerary = None
if "original_query" not in st.session_state:
    st.session_state.original_query = ""
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []

# Custom CSS for enhanced aesthetics
st.markdown("""
    <style>
    /* Main background gradient */
    .stApp {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    }
    
    /* Header styling */
    .main-header {
        text-align: center;
        padding: 2rem 0;
        color: white;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
    }
    
    .main-header h1 {
        font-size: 3.5rem;
        font-weight: 700;
        margin-bottom: 0.5rem;
        animation: fadeInDown 0.8s ease-in;
    }
    
    .main-header p {
        font-size: 1.3rem;
        opacity: 0.95;
        animation: fadeInUp 0.8s ease-in;
    }
    
    /* Input container */
    .input-container {
        background: rgba(255, 255, 255, 0.95);
        padding: 2.5rem;
        border-radius: 20px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        margin: 2rem auto;
        max-width: 800px;
        backdrop-filter: blur(10px);
    }
    
    /* Feedback container */
    .feedback-container {
        background: rgba(255, 255, 255, 0.95);
        padding: 2rem;
        border-radius: 20px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.3);
        margin: 2rem auto;
        max-width: 800px;
        backdrop-filter: blur(10px);
    }
    
    /* Itinerary card */
    .itinerary-card {
        background: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        margin: 1rem 0;
        animation: slideIn 0.5s ease-out;
        color: #2d3748;
    }
    
    .day-header {
        color: #667eea;
        font-size: 1.5rem;
        font-weight: 600;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 3px solid #667eea;
    }
    
    .activity-item {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1rem;
        border-radius: 10px;
        margin: 0.8rem 0;
        border-left: 4px solid #764ba2;
        color: #2d3748;
        font-size: 1rem;
    }
    
    /* Conversation bubble */
    .conversation-bubble {
        background: #f0f4ff;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
        border-left: 4px solid #667eea;
        color: #2d3748;
    }
    
    /* Animations */
    @keyframes fadeInDown {
        from {
            opacity: 0;
            transform: translateY(-20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateX(-20px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
    
    /* Button styling */
    .stButton > button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-size: 1.2rem;
        font-weight: 600;
        padding: 0.8rem 3rem;
        border-radius: 50px;
        border: none;
        box-shadow: 0 10px 25px rgba(102, 126, 234, 0.4);
        transition: all 0.3s ease;
        width: 100%;
    }
    
    .stButton > button:hover {
        transform: translateY(-3px);
        box-shadow: 0 15px 35px rgba(102, 126, 234, 0.6);
    }
    
    /* Input field styling */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        border-radius: 10px;
        border: 2px solid #e0e0e0;
        padding: 1rem;
        font-size: 1.1rem;
        transition: all 0.3s ease;
    }
    
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {
        border-color: #667eea;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

def generate_itinerary_request(query):
    """Make API request to generate itinerary"""
    try:
        # Try v2 endpoint first (LangGraph), fallback to v1
        response = requests.post(
            "http://127.0.0.1:8000/itinerary/v2",
            json={"query": query},
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json(), None
        else:
            return None, "❌ Oops! We couldn't generate your itinerary. Please try again."
            
    except requests.exceptions.Timeout:
        return None, "⏱️ Request timed out. Please try again."
    except requests.exceptions.ConnectionError:
        return None, "🔌 Could not connect to the server. Make sure it's running on http://127.0.0.1:8000"
    except Exception as e:
        return None, f"❌ An error occurred: {str(e)}"

def display_itinerary(itinerary_text):
    """Display the itinerary in formatted cards"""
    if itinerary_text:
        # Split by days
        days = itinerary_text.split("🗓️ Day ")
        days = [d.strip() for d in days if d.strip()]
        
        for day_text in days:
            lines = day_text.split("\n")
            day_num = lines[0].strip() if lines else "?"
            
            with st.container():
                st.markdown('<div class="itinerary-card">', unsafe_allow_html=True)
                st.markdown(f'<div class="day-header">🗓️ Day {day_num}</div>', unsafe_allow_html=True)
                
                current_time = None
                for line in lines[1:]:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Check if it's a time header (☀️ Morning:, etc.)
                    if line.startswith("☀️") or line.startswith("🌤️") or line.startswith("🌙"):
                        current_time = line
                        st.markdown(f'<p style="font-weight: 600; color: #764ba2; margin-top: 1rem; font-size: 1.1rem;">{line}</p>', unsafe_allow_html=True)
                    elif line.startswith("-"):
                        # Activity item
                        activity_text = line[1:].strip()
                        st.markdown(f'<div class="activity-item">{activity_text}</div>', unsafe_allow_html=True)
                
                st.markdown('</div>', unsafe_allow_html=True)

# Header
st.markdown("""
    <div class="main-header">
        <h1>🌍 Pack & Go</h1>
        <p>Your AI-Powered Travel Companion</p>
    </div>
""", unsafe_allow_html=True)

# Main content
if not st.session_state.itinerary_generated:
    # Initial query input
    col1, col2, col3 = st.columns([1, 3, 1])
    
    with col2:
        st.markdown('<div class="input-container">', unsafe_allow_html=True)
        
        query = st.text_input(
            "✈️ Where do you want to go?",
            placeholder="e.g., 3-day trip to Paris, France",
            label_visibility="visible",
            key="initial_query"
        )
        
        st.write("")  # Spacing
        
        if st.button("🚀 Generate My Itinerary", key="generate_btn"):
            if query.strip():
                with st.spinner("✨ Crafting your perfect itinerary..."):
                    data, error = generate_itinerary_request(query)
                    
                    if error:
                        st.error(error)
                    elif data:
                        st.session_state.current_itinerary = data
                        st.session_state.structured_itinerary = data.get("structured", {})
                        st.session_state.original_query = query
                        st.session_state.itinerary_generated = True
                        st.session_state.conversation_history = [
                            {"role": "user", "content": query},
                            {"role": "assistant", "content": "itinerary_generated"}
                        ]
                        st.rerun()
            else:
                st.warning("⚠️ Please enter a destination to generate an itinerary!")
        
        st.markdown('</div>', unsafe_allow_html=True)

else:
    # Display current itinerary and feedback section
    st.markdown("---")
    st.markdown("<h2 style='text-align: center; color: white; margin: 2rem 0;'>📅 Your Personalized Itinerary</h2>", unsafe_allow_html=True)
    
    # Display itinerary
    col1, col2, col3 = st.columns([1, 6, 1])
    with col2:
        itinerary_text = st.session_state.current_itinerary.get("itinerary", "")
        display_itinerary(itinerary_text)
        
        # Download button
        st.markdown("---")
        st.download_button(
            label="📥 Download Itinerary",
            data=itinerary_text,
            file_name="my_travel_itinerary.txt",
            mime="text/plain",
            use_container_width=True
        )
    
    # Feedback section
    st.markdown("---")
    st.markdown("<h3 style='text-align: center; color: white; margin: 2rem 0;'>💬 Want to refine your itinerary?</h3>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        st.markdown('<div class="feedback-container">', unsafe_allow_html=True)
        
        # Show conversation history
        if len(st.session_state.conversation_history) > 2:
            st.markdown("<p style='font-weight: 600; color: #667eea; margin-bottom: 1rem;'>Conversation History:</p>", unsafe_allow_html=True)
            
            for i, msg in enumerate(st.session_state.conversation_history[2:], 1):
                if msg["role"] == "user":
                    st.markdown(f'<div class="conversation-bubble"><strong>You:</strong> {msg["content"]}</div>', unsafe_allow_html=True)
                elif msg["role"] == "assistant" and msg["content"] != "itinerary_generated":
                    st.markdown(f'<div class="conversation-bubble"><strong>Assistant:</strong> Updated itinerary based on your feedback!</div>', unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
        
        feedback = st.text_area(
            "Share your feedback:",
            placeholder="e.g., 'I'd like more museum visits and fewer shopping areas' or 'Can we add more local food experiences?'",
            height=100,
            key="feedback_input"
        )
        
        col_a, col_b = st.columns(2)
        
        with col_a:
            if st.button("🔄 Regenerate Itinerary", key="regenerate_btn", use_container_width=True):
                if feedback.strip():
                    with st.spinner("✨ Updating your itinerary..."):
                        # Use the new /refine endpoint with structured data
                        try:
                            response = requests.post(
                                "http://127.0.0.1:8000/itinerary/refine",
                                json={
                                    "query": st.session_state.original_query,
                                    "feedback": feedback,
                                    "current_itinerary": st.session_state.structured_itinerary
                                },
                                timeout=30
                            )
                            
                            if response.status_code == 200:
                                data = response.json()
                                st.session_state.current_itinerary = data
                                st.session_state.structured_itinerary = data.get("structured", {})
                                st.session_state.conversation_history.append({"role": "user", "content": feedback})
                                st.session_state.conversation_history.append({"role": "assistant", "content": "itinerary_generated"})
                                st.rerun()
                            else:
                                st.error("❌ Failed to update itinerary")
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
                else:
                    st.warning("⚠️ Please share your feedback before regenerating!")
        
        with col_b:
            if st.button("🆕 Start New Trip", key="new_trip_btn", use_container_width=True):
                st.session_state.itinerary_generated = False
                st.session_state.current_itinerary = None
                st.session_state.structured_itinerary = None
                st.session_state.original_query = ""
                st.session_state.conversation_history = []
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)

# Footer
st.markdown("---")
st.markdown("""
    <div style='text-align: center; color: white; padding: 2rem; opacity: 0.9;'>
        <p>✨ Powered by AI | Made with ❤️ for travelers</p>
    </div>
""", unsafe_allow_html=True)