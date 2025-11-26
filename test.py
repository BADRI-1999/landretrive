import requests
from bs4 import BeautifulSoup
import csv

BASE = "https://bhulekh.mahabhumi.gov.in/mahabhumi"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0",
    "Accept": "*/*",
    "Referer": "https://bhulekh.mahabhumi.gov.in/",
    "X-Requested-With": "XMLHttpRequest"
})

def get_options(url):
    r = session.get(url)
    soup = BeautifulSoup(r.text, "lxml")

    data = []
    for opt in soup.find_all("option"):
        val = opt.get("value")
        name = opt.text.strip()
        if val != "0":   # skip "Please select"
            data.append({"code": val, "name": name})
    return data


# ---------- SCRAPING ----------
file = open("maharashtra_land_data.csv", "w", newline="", encoding="utf-8")
w = csv.writer(file)
w.writerow(["district", "taluka", "village", "survey_no"])

# 1) Districts
districts = get_options(f"{BASE}/GetDistrict")

for d in districts:
    print("District:", d["name"])
    talukas = get_options(f"{BASE}/GetTaluka?district_code={d['code']}")

    for t in talukas:
        print("  Taluka:", t["name"])
        villages = get_options(
            f"{BASE}/GetVillage?district_code={d['code']}&taluka_code={t['code']}"
        )

        for v in villages:
            print("    Village:", v["name"])
            surveys = get_options(
                f"{BASE}/getSurvey?district_code={d['code']}&taluka_code={t['code']}&village_code={v['code']}"
            )

            for s in surveys:
                w.writerow([d["name"], t["name"], v["name"], s["name"]])

file.close()
print("\n✔ DONE — ALL DATA EXTRACTED")
