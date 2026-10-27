import os
import s3fs
from dotenv import load_dotenv

load_dotenv()
fs = s3fs.S3FileSystem(
    key=os.getenv("AWS_ACCESS_KEY_ID"),
    secret=os.getenv("AWS_SECRET_ACCESS_KEY"),
)

todas = [r for r in fs.find("data-steven/data_lake") if not r.endswith("/")]
total_bytes = 0
print("OBJETOS EN data_lake/:")
for r in sorted(todas):
    size = fs.info(r).get("size", 0) or 0
    total_bytes += size
    print(f"  {r}  {size/1024/1024:.1f} MB")

escala = [r for r in todas if "/scale/" in r]
bytes_escala = sum(fs.info(r).get("size", 0) or 0 for r in escala)
print(f"\nTOTAL data_lake/: {len(todas)} archivos, {total_bytes/1024**3:.3f} GB")
print(f"TOTAL scale/    : {len(escala)} archivos, {bytes_escala/1024**3:.3f} GB")
