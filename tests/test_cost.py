from app.cost import calculate_cost

def test_calculate_cost():
    # gpt-4o input: 5.00, output: 15.00
    cost = calculate_cost("openai", "gpt-4o", 1_000_000, 1_000_000)
    assert cost == 20.00
    
    cost_small = calculate_cost("openai", "gpt-4o", 1000, 1000)
    assert cost_small == 0.02
    
def test_calculate_cost_unknown_model():
    assert calculate_cost("openai", "unknown-model", 100, 100) is None

def test_calculate_cost_ollama():
    assert calculate_cost("ollama", "llama3", 1000, 1000) == 0.0
