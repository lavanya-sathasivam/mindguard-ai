def calculate_phq9_score(answers: list[int]) -> dict:
    # Validate answers (should be a list of 9 integers, 0-3)
    if len(answers) != 9:
        raise ValueError("PHQ-9 requires exactly 9 answers.")
        
    score = sum(answers)
    classification = "Minimal depression"
    
    if score >= 20:
        classification = "Severe depression"
    elif score >= 15:
        classification = "Moderately severe depression"
    elif score >= 10:
        classification = "Moderate depression"
    elif score >= 5:
        classification = "Mild depression"
        
    return {
        "score": score,
        "classification": classification
    }
