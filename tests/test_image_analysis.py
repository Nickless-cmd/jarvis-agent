#!/usr/bin/env python3
"""
Test script for image analysis hallucination fixes
"""
import base64
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, 'src')

def test_image_analysis_raw():
    """Test image analysis with raw Ollama response (bypassing hallucination detection)"""
    # Test both images
    test_images = [
        ("BIMI SVG", "src/data/workspaces/bs/uploads/416fc668790449e2819ab4bdb3349d2e_bimi-svg-tiny-12-ps.svg"),
        ("PNG Image", "src/data/workspaces/bs/uploads/481311e99ae44299be0dc6d6fe70aa1d_122ca642.png")
    ]

    for image_name, image_path in test_images:
        print(f"\n🖼️  Testing {image_name}: {image_path}")

        if not os.path.exists(image_path):
            print(f"❌ Image not found: {image_path}")
            continue

        # Read and encode image
        try:
            with open(image_path, "rb") as f:
                image_data = f.read()
            b64 = base64.b64encode(image_data).decode("utf-8")
            print(f"✅ Image loaded and encoded ({len(b64)} chars)")
        except Exception as e:
            print(f"❌ Failed to load image: {e}")
            continue

        # Direct Ollama call bypassing hallucination detection
        try:
            import requests
            url = "http://127.0.0.1:11434/api/generate"
            prompt = (
                "BESKRIV KUN DET DU KAN SE DIREKTE PÅ BILLEDET. "
                "INGEN GÆT, INGEN FORMODNINGER, INGEN STEDNAVNE, INGEN PERSONER, INGEN AKTIVITETER. "
                "Hvis du er usikker på noget, sig 'Jeg kan ikke se det klart'. "
                "Vær kort og præcis."
            )

            payload = {
                "model": "llava:latest",
                "prompt": prompt,
                "images": [b64],
                "stream": False,
                "options": {"num_ctx": 2048},
            }

            print("🔍 Calling Ollama directly...")
            resp = requests.post(url, json=payload, timeout=60)

            if resp.ok:
                data = resp.json()
                raw_text = (data.get("response") or "").strip()
                print(f"📝 Raw Ollama response: '{raw_text}'")

                # Check for hallucinations
                hallucination_indicators = [
                    "scene", "aktivitet", "mennesker", "objekter", "situation", "handling",
                    "bevæger sig", "står", "sidder", "kigger", "ser", "betragter",
                    "formodentlig", "antagelig", "sandsynligvis", "troligt", "troligvis",
                    "københavn", "danmark", "europa", "verden", "by", "gade", "hus",
                    "familie", "venner", "turist", "rejse", "ferie", "morgen", "aften"
                ]

                found_hallucinations = []
                for indicator in hallucination_indicators:
                    if indicator.lower() in raw_text.lower():
                        found_hallucinations.append(indicator)

                if found_hallucinations:
                    print(f"⚠️  Hallucinations detected: {', '.join(found_hallucinations)}")
                    print("❌ Would be blocked by our detection")
                else:
                    print("✅ No hallucinations detected - would pass through")
            else:
                print(f"❌ Ollama error: {resp.status_code} - {resp.text[:200]}")

        except Exception as e:
            print(f"❌ Error calling Ollama: {e}")

def test_image_analysis_with_detection():
    """Test the full pipeline with hallucination detection"""
    from jarvis.agent import _describe_image_ollama

    # Test the problematic PNG image
    image_path = "src/data/workspaces/bs/uploads/481311e99ae44299be0dc6d6fe70aa1d_122ca642.png"

    if not os.path.exists(image_path):
        print(f"❌ Test image not found: {image_path}")
        return

    try:
        with open(image_path, "rb") as f:
            image_data = f.read()
        b64 = base64.b64encode(image_data).decode("utf-8")
        print(f"✅ PNG image loaded and encoded ({len(b64)} chars)")
    except Exception as e:
        print(f"❌ Failed to load image: {e}")
        return

    # Enable debug logging
    os.environ["JARVIS_DEBUG_IMAGE"] = "1"

    print("🔍 Testing full pipeline with hallucination detection...")
    text, error = _describe_image_ollama(b64, is_admin=True, ui_lang="da")

    print("\n📊 Full pipeline results:")
    print(f"Text: {text}")
    print(f"Error: {error}")

if __name__ == "__main__":
    print("=== Raw Ollama Response Test ===")
    test_image_analysis_raw()

    print("\n=== Full Pipeline Test ===")
    test_image_analysis_with_detection()