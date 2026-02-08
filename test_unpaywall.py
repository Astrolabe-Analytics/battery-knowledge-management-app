import requests
import json

# Test 3 DOIs that failed in the bulk search
test_dois = [
    "10.3390/en13102638",  # Stampatori 2020 - Energies
    "10.1016/j.rser.2018.03.002",  # Zubi 2018 - Renewable Energy
    "10.1016/j.est.2021.103112",  # Jyoti 2021 - Energy Storage
]

emails_to_test = [
    "user@example.com",  # What the script is currently using
    "researcher@example.com",  # Alternative
]

for email in emails_to_test:
    print(f"\n{'='*60}")
    print(f"Testing with email: {email}")
    print('='*60)

    for doi in test_dois:
        print(f"\nDOI: {doi}")
        url = f"https://api.unpaywall.org/v2/{doi}"
        params = {'email': email}

        try:
            response = requests.get(url, params=params, timeout=10)
            print(f"Status Code: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                print(f"is_oa: {data.get('is_oa')}")
                print(f"oa_status: {data.get('oa_status')}")

                if data.get('best_oa_location'):
                    oa_loc = data['best_oa_location']
                    print(f"best_oa_location.url: {oa_loc.get('url')}")
                    print(f"best_oa_location.url_for_pdf: {oa_loc.get('url_for_pdf')}")
                    print(f"best_oa_location.url_for_landing_page: {oa_loc.get('url_for_landing_page')}")
                else:
                    print("No best_oa_location found")

            else:
                print(f"Error response: {response.text[:500]}")

        except Exception as e:
            print(f"Exception: {e}")

    break  # Only test first email if it works
