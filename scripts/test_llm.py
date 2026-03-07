"""Test LLM integration by creating a property and enriching it."""
import sys
import asyncio
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from packages.storage.database import get_session
from packages.storage.models import Property, Source
from packages.ai.bedrock_provider import BedrockProvider
from packages.shared.config import get_settings

async def test_llm():
    config = get_settings()
    
    # Create test property
    with get_session() as db:
        # Get first source
        source = db.query(Source).first()
        if not source:
            print("[ERROR] No sources found. Run: python scripts/seed.py")
            return
        
        # Check if test property exists
        test_prop = db.query(Property).filter(Property.title == "Test Property for LLM").first()
        
        if not test_prop:
            import hashlib
            title = "Test Property for LLM"
            description = "Beautiful 3-bedroom house in Dublin with modern kitchen, spacious garden, and excellent transport links. Recently renovated with energy-efficient features."
            price = 450000
            content = f"{title}{description}{price}"
            content_hash = hashlib.md5(content.encode()).hexdigest()
            
            test_prop = Property(
                source_id=source.id,
                external_id="test-llm-001",
                url="https://example.com/test",
                title=title,
                description=description,
                address="123 Test Street, Dublin 2",
                county="Dublin",
                price=price,
                property_type="house",
                sale_type="sale",
                bedrooms=3,
                bathrooms=2,
                floor_area_sqm=120,
                ber_rating="B2",
                status="active",
                content_hash=content_hash
            )
            db.add(test_prop)
            db.commit()
            db.refresh(test_prop)
            print(f"[OK] Created test property: {test_prop.id}")
        else:
            print(f"[OK] Using existing test property: {test_prop.id}")
        
        property_id = test_prop.id
    
    # Test LLM enrichment
    print("\n[TEST] Testing Bedrock LLM integration...")
    print(f"Provider: {config.llm_provider}")
    print(f"Model: {config.bedrock_model_id}")
    
    if config.llm_provider != "bedrock":
        print(f"\n[WARN] LLM provider is set to '{config.llm_provider}', not 'bedrock'")
        print("Set LLM_PROVIDER=bedrock in .env file to test Bedrock")
        return 0
    
    try:
        provider = BedrockProvider()
        
        # Test property data
        property_data = {
            "title": "Test Property for LLM",
            "description": "Beautiful 3-bedroom house in Dublin with modern kitchen, spacious garden, and excellent transport links. Recently renovated with energy-efficient features.",
            "price": 450000,
            "bedrooms": 3,
            "bathrooms": 2,
            "floor_area_sqm": 120,
            "ber_rating": "B2",
            "county": "Dublin"
        }
        
        print("\n[TEST] Generating property summary...")
        summary_prompt = f"""Summarize this property in 2-3 sentences:
Title: {property_data['title']}
Description: {property_data['description']}
Price: €{property_data['price']:,}
Bedrooms: {property_data['bedrooms']}
County: {property_data['county']}"""
        
        response = await provider.generate(summary_prompt, max_tokens=200)
        print(f"\n[RESULT] Summary:\n{response.content}\n")
        
        print("[TEST] Generating value assessment...")
        value_prompt = f"""Rate this property's value on a scale of 1-10 and explain why:
Price: €{property_data['price']:,}
Bedrooms: {property_data['bedrooms']}
Area: {property_data['floor_area_sqm']}sqm
BER: {property_data['ber_rating']}
County: {property_data['county']}

Respond in JSON format: {{"score": <number>, "reasoning": "<text>"}}"""
        
        value_response = await provider.generate(value_prompt, json_mode=True, max_tokens=300)
        try:
            value = json.loads(value_response.content)
        except:
            value = {"score": "N/A", "reasoning": value_response.content}
        print(f"\n[RESULT] Value Score: {value.get('score', 'N/A')}/10")
        print(f"Reasoning: {value.get('reasoning', 'N/A')}\n")
        
        print("[TEST] Generating pros/cons...")
        pros_cons_prompt = f"""List 3 pros and 3 cons for this property:
{property_data['description']}
Price: €{property_data['price']:,}
BER: {property_data['ber_rating']}

Respond in JSON format: {{"pros": ["...", "...", "..."], "cons": ["...", "...", "..."]}}"""
        
        pros_cons_response = await provider.generate(pros_cons_prompt, json_mode=True, max_tokens=400)
        try:
            pros_cons = json.loads(pros_cons_response.content)
        except:
            pros_cons = {"pros": [], "cons": []}
        print(f"\n[RESULT] Pros:")
        for pro in pros_cons.get('pros', []):
            print(f"  + {pro}")
        print(f"\n[RESULT] Cons:")
        for con in pros_cons.get('cons', []):
            print(f"  - {con}")
        
        print("\n[SUCCESS] LLM integration test passed!")
        
    except Exception as e:
        print(f"\n[ERROR] LLM test failed: {e}")
        print("\nMake sure:")
        print("1. AWS credentials are configured (aws configure)")
        print("2. Bedrock model access is enabled in AWS Console")
        print("3. Region is set correctly (eu-west-1 or us-east-1)")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(test_llm()))
