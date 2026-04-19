import json
import os
from typing import List, Dict

# Load strategies from data
data_path = os.path.join(os.path.dirname(__file__), '../../data/coping_strategies.json')

def load_strategies() -> List[dict]:
    try:
        if os.path.exists(data_path):
            with open(data_path, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Error loading coping strategies: {e}")
    return []

def get_recommendations_for_emotion(emotion: str) -> List[dict]:
    strategies = load_strategies()
    emotion = emotion.lower()
    
    # Simple mapping
    mapping = {
        "fear": "anxiety",
        "joy": "joy",
        "anger": "anger",
        "sadness": "sadness",
        "disgust": "anger",
        "surprise": "anxiety", # Usually surprise invokes some anxiety
        "neutral": "stress" # Fallback
    }
    
    target_emotion = mapping.get(emotion, "stress")
    
    for state in strategies:
        if state["emotion"] == target_emotion:
            return state["strategies"]
            
    # Fallback
    for state in strategies:
        if state["emotion"] == "stress":
            return state["strategies"]
            
    return [{"title": "Take a breath", "description": "Just take a deep breath.", "type": "mindfulness"}]

