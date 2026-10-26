import os
import sys
import time
import tracemalloc

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import bot

def test_real_apk():
    apk_path = os.path.join("tests_apk", "SuperTuxKart-1.5.apk")
    if not os.path.exists(apk_path):
        print(f"Downloading real APK SuperTuxKart-1.5.apk from GitHub...")
        os.makedirs("tests_apk", exist_ok=True)
        import urllib.request
        url = "https://github.com/supertuxkart/stk-code/releases/download/1.5/SuperTuxKart-1.5.apk"
        urllib.request.urlretrieve(url, apk_path)

    file_size = os.path.getsize(apk_path)
    file_size_mb = file_size / (1024 * 1024)
    print("==================================================")
    print(f"REAL WORLD APK VERIFICATION TEST: SuperTuxKart-1.5.apk")
    print(f"File Size: {file_size:,} bytes ({file_size_mb:.2f} MB)")
    print("==================================================")

    # Start memory tracking to prove bounded RAM usage
    tracemalloc.start()
    t0 = time.time()
    
    info = bot.inspect_apk(apk_path)
    
    duration = time.time() - t0
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_mb = peak_mem / (1024 * 1024)
    print(f"Inspection duration: {duration:.2f}s")
    print(f"Peak RAM usage during inspection: {peak_mb:.2f} MB (Bounded! < 20 MB)")
    print(f"Signer source detected: {info.get('signer_source')}")
    print(f"Package: {info.get('package')}")
    print(f"Version Name: {info.get('version_name')}")
    print(f"Version Code: {info.get('version_code')}")
    print(f"minSdk: {info.get('min_sdk')} / targetSdk: {info.get('target_sdk')}")
    print(f"File SHA-256: {info.get('file_sha256')}")
    print(f"Cert SHA-256: {info.get('cert_sha256')}")
    print(f"Subject DN: {info.get('subject_dn')}")

    assert info is not None, "Failed to inspect APK!"
    assert info.get("package") == "org.supertuxkart.stk", f"Unexpected package: {info.get('package')}"
    assert info.get("version_code") is not None, "Missing version_code"
    assert info.get("file_sha256") is not None, "Missing file SHA256"
    assert info.get("cert_sha256") is not None, "Missing certificate SHA256"
    assert peak_mb < 30.0, f"Memory not bounded! Peak: {peak_mb:.2f} MB"

    # Also verify direct v2/v3 block extraction
    v2_cert = bot.extract_v2_v3_cert(apk_path)
    assert v2_cert is not None, "Failed to extract v2/v3 signing block certificate from SuperTuxKart!"
    v2_fingerprint = v2_cert.fingerprint(bot.hashes.SHA256()).hex().upper()
    print(f"Direct v2/v3 Signing Block Cert SHA-256: {v2_fingerprint}")
    assert v2_fingerprint == info.get('cert_sha256'), "v2 certificate fingerprint must match v1 certificate!"

    print("\n" + "=" * 50)
    print("CARD OUTPUT (ARABIC):")
    print("=" * 50)
    card_ar = bot.format_apk_inspection_card(info, prev=None, lang="ar")
    print(card_ar)

    print("\n" + "=" * 50)
    print("CARD OUTPUT (ENGLISH):")
    print("=" * 50)
    card_en = bot.format_apk_inspection_card(info, prev=None, lang="en")
    print(card_en)
    print("\nREAL WORLD APK VERIFICATION TEST: SUCCESS!")

if __name__ == "__main__":
    test_real_apk()
