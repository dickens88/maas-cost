import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

HW_AK = os.environ.get("HW_AK", "")
HW_SK = os.environ.get("HW_SK", "")
HW_REGION = os.environ.get("HW_REGION", "cn-southwest-2")
# Optional; resolved from IAM by region name when empty
HW_PROJECT_ID = os.environ.get("HW_PROJECT_ID", "")
IAM_ENDPOINT = os.environ.get("IAM_ENDPOINT", "https://iam.myhuaweicloud.com")
MAAS_ENDPOINT = os.environ.get("MAAS_ENDPOINT", f"https://modelarts.{HW_REGION}.myhuaweicloud.com")

# Display timezone offset in hours
TZ_OFFSET_HOURS = int(os.environ.get("TZ_OFFSET_HOURS", "8"))
# Stay under the 200/min per-user limit enforced by MaaS
RATE_LIMIT_PER_MIN = int(os.environ.get("RATE_LIMIT_PER_MIN", "150"))
# In-memory cache for windows that are still open / already closed
CACHE_TTL_OPEN_SEC = int(os.environ.get("CACHE_TTL_OPEN_SEC", "300"))
CACHE_TTL_CLOSED_SEC = int(os.environ.get("CACHE_TTL_CLOSED_SEC", "3600"))
API_CONCURRENCY = int(os.environ.get("API_CONCURRENCY", "4"))

FRONTEND_DIST = ROOT / "frontend" / "dist"
