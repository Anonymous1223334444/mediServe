# scripts/monitor_indexing.py
import time
from documents.models import DocumentUpload
import models

while True:
    stats = DocumentUpload.objects.values('upload_status').annotate(
        count=models.Count('id')
    )
    
    print("\033[2J\033[H")  # Clear screen
    print("=== INDEXING STATUS ===")
    for stat in stats:
        print(f"{stat['upload_status']}: {stat['count']}")
    
    time.sleep(2)