import asyncio
import csv
from urllib.parse import quote

import httpx

BASE = "https://bhubharati.telangana.gov.in"

# ---- headers + cookies from your cURL ----
COMMON_HEADERS = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Content-type": "application/x-www-form-urlencoded",
    "Referer": f"{BASE}/knowLandStatus",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
    "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

COOKIES = {
    # IMPORTANT: update this from DevTools whenever session changes
    "org.springframework.web.servlet.i18n.CookieLocaleResolver.LOCALE": "en",
    "JSESSIONID": "Xa0fz-ruigEdhouy4rMYzswrJcjkbzj_izrB9cC9.dharani-app-prod01",
}

# Limit total concurrent HTTP calls
MAX_CONCURRENCY = 10
_sem = asyncio.Semaphore(MAX_CONCURRENCY)


def pick(d: dict, *keys, default=None):
    """Safely pick first non-empty field from dict using possible key names."""
    for k in keys:
        v = d.get(k)
        if v not in (None, "", "--", "--నివ్వండి--"):
            return v
    return default


async def fetch_json(client: httpx.AsyncClient, url: str, label: str):
    """GET url -> JSON (or None). Logs issues and first 120 chars on non-JSON."""
    async with _sem:
        try:
            r = await client.get(url, timeout=30)
        except Exception as e:
            print(f"[{label}] ❌ network error: {e}")
            return None

    if r.status_code != 200:
        print(f"[{label}] ❌ HTTP {r.status_code}")
        return None

    try:
        return r.json()
    except Exception:
        text = r.text[:120].replace("\n", " ")
        print(f"[{label}] ⚠ NOT JSON, first bytes: {text!r}")
        return None


# ============ API wrappers ============

async def get_mandals(client: httpx.AsyncClient, district_id: int):
    url = f"{BASE}/getMandalFromDivisionCitizenPortal?district={district_id}"
    return await fetch_json(client, url, f"mandals d={district_id}") or []


async def get_villages(client: httpx.AsyncClient, mandal_id: int):
    url = f"{BASE}/getVillageFromMandalCitizenPortal?mandalId={mandal_id}"
    return await fetch_json(client, url, f"villages m={mandal_id}") or []


async def get_surveys(client: httpx.AsyncClient, village_id: int):
    url = f"{BASE}/getSurveyCitizen?villId={village_id}&flag=survey"
    return await fetch_json(client, url, f"surveys v={village_id}") or []


async def get_khatas(client: httpx.AsyncClient, village_id: int, survey_no: str):
    enc_survey = quote(survey_no, safe="/")
    url = (
        f"{BASE}/getKhataNoCitizen"
        f"?villId={village_id}&flag=khatanos&surveyNo={enc_survey}"
    )
    return await fetch_json(client, url, f"khatas v={village_id} s={survey_no}") or []


# ============ processing coroutines ============

async def process_village(
    client: httpx.AsyncClient,
    district_id: int,
    mandal_id: int,
    village: dict,
    village_rows: list,
    survey_rows: list,
    khata_rows: list,
):
    vill_id = pick(village, "villId", "villageId", "id")
    vill_name = pick(village, "villName", "villageName", "name", "text", default="")
    if not vill_id:
        return

    village_rows.append([mandal_id, vill_id, vill_name])

    # Surveys
    surveys = await get_surveys(client, int(vill_id))
    if not surveys:
        print(f"[NO SURVEYS] dist={district_id} mandal={mandal_id} village={vill_id} {vill_name}")
        return

    survey_nos = []
    for s in surveys:
        s_no = pick(s, "surveyNo", "surveyNumber", "value", "id")
        if not s_no:
            continue
        survey_nos.append(s_no)
        survey_rows.append([vill_id, s_no])

    if not survey_nos:
        print(f"[NO VALID SURVEY NOS] v={vill_id}")
        return

    # Khatas in parallel per survey
    tasks = [get_khatas(client, int(vill_id), s_no) for s_no in survey_nos]
    khata_lists = await asyncio.gather(*tasks)

    for s_no, khatas in zip(survey_nos, khata_lists):
        if not khatas:
            print(f"[NO KHATAS] dist={district_id} mandal={mandal_id} village={vill_id} survey={s_no}")
            continue

        for kh in khatas:
            kh_no = pick(kh, "khataNo", "khataNumber", "value", "id")
            if not kh_no:
                continue
            khata_rows.append([vill_id, s_no, kh_no])


async def process_mandal(
    client: httpx.AsyncClient,
    district_id: int,
    mandal: dict,
    mandal_rows: list,
    village_rows: list,
    survey_rows: list,
    khata_rows: list,
):
    mandal_id = pick(mandal, "mandalId", "mandalid", "id")
    mandal_name = pick(mandal, "mandalName", "name", "text", default="")
    if not mandal_id:
        return

    mandal_id_int = int(mandal_id)
    mandal_rows.append([district_id, mandal_id_int, mandal_name])

    villages = await get_villages(client, mandal_id_int)
    if not villages:
        print(f"[NO VILLAGES] dist={district_id} mandal={mandal_id_int} {mandal_name}")
        return

    # Run all villages for this mandal in parallel
    await asyncio.gather(
        *[
            process_village(
                client,
                district_id,
                mandal_id_int,
                v,
                village_rows,
                survey_rows,
                khata_rows,
            )
            for v in villages
        ]
    )


async def run_pipeline(district_ids: list[int]):
    mandal_rows: list[list] = []
    village_rows: list[list] = []
    survey_rows: list[list] = []
    khata_rows: list[list] = []

    async with httpx.AsyncClient(
        headers=COMMON_HEADERS,
        cookies=COOKIES,
        timeout=30,
    ) as client:
        for d_id in district_ids:
            print(f"\n=== District {d_id} ===")
            mandals = await get_mandals(client, d_id)
            if not mandals:
                print(f"[NO MANDALS] district={d_id}")
                continue

            # Run all mandals for this district in parallel
            await asyncio.gather(
                *[
                    process_mandal(
                        client,
                        d_id,
                        m,
                        mandal_rows,
                        village_rows,
                        survey_rows,
                        khata_rows,
                    )
                    for m in mandals
                ]
            )

    return mandal_rows, village_rows, survey_rows, khata_rows


def save_csv(path: str, header: list[str], rows: list[list]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print(f"💾 Saved {len(rows)} rows to {path}")


def main():
    # Example: district 13 only (from your cURL). Add more if needed.
    district_ids = [13]

    mandal_rows, village_rows, survey_rows, khata_rows = asyncio.run(
        run_pipeline(district_ids)
    )

    save_csv("mandal.csv", ["district_id", "mandal_id", "mandal_name"], mandal_rows)
    save_csv("village.csv", ["mandal_id", "village_id", "village_name"], village_rows)
    save_csv("survey.csv", ["village_id", "survey_no"], survey_rows)
    save_csv("khata.csv", ["village_id", "survey_no", "khata_no"], khata_rows)


if __name__ == "__main__":
    main()
