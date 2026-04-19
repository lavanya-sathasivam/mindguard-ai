from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from transformers import pipeline

# Initialize models
print("Loading VADER sentiment analyzer...")
analyzer = SentimentIntensityAnalyzer()

print("Loading HuggingFace emotion classifier pipeline...")
# Note: In a real production app, we would load the tokenizer and model explicitly and handle batching.
# Using a popular, lightweight emotion model. 
try:
    emotion_classifier = pipeline("text-classification", model="j-hartmann/emotion-english-distilroberta-base", top_k=1)
except Exception as e:
    print(f"Warning: Could not load emotion model: {e}")
    # Fallback to a mock for local dev if internet/installation fails
    emotion_classifier = None

def analyze_message_emotion(text: str) -> dict:
    # 1. Sentiment Score with VADER
    sentiment = analyzer.polarity_scores(text)
    compound_score = sentiment['compound'] # -1.0 to 1.0
    
    # 2. Emotion Classification with Transformers
    emotion_label = "neutral"
    if emotion_classifier:
        try:
            results = emotion_classifier(text, truncation=True, max_length=128)
            if results and len(results) > 0 and len(results[0]) > 0:
                emotion_label = results[0][0]['label'] # e.g., 'joy', 'anger', 'sadness', 'fear', 'surprise', 'disgust', 'neutral'
        except Exception as e:
            print(f"Emotion classification failed: {e}")
            emotion_label = "unknown"
            
    # Calculate simple risk level based on sentiment
    risk_level = "Low"
    if compound_score < -0.5:
        risk_level = "Moderate"
    if compound_score < -0.8 or emotion_label in ["fear", "sadness", "anger", "disgust"] and compound_score < -0.6:
        risk_level = "High"

    return {
        "emotion": emotion_label,
        "sentiment_score": round(compound_score, 2),
        "risk_level": risk_level
    }
