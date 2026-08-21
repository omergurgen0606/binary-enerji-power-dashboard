import hashlib
import hmac
import os
import sys


def main():
    if len(sys.argv) != 2:
        print("Kullanim: python generate_claim_code.py <device_id>")
        sys.exit(1)

    device_id = sys.argv[1]
    secret = os.environ["DEVICE_CLAIM_SECRET"]
    digest = hmac.new(secret.encode(), device_id.strip().lower().encode(), hashlib.sha256).hexdigest()
    code = digest[:6].upper()
    print(f"device_id: {device_id}")
    print(f"kurulum kodu: {code}")
    print("Bu ikisini cihazin etiketine/kutusuna birlikte yazin.")


if __name__ == "__main__":
    main()
