### Waiting List
```
Vietnamese Title | Desired Chapters | 🍅 Book ID | Desired Date (optional)
```
### Uploading List
```
🟦 Book ID | Uploaded Chapters | 🍅 Book ID
```
### Issue Commands 

| Issue Title | Body Format |
|---|---|
| `ADD_WAITING` | `Vi Title \| desired_ch \| 🍅_id` (one per line) |
| `ADD_UPLOADING` | `🟦_id \| uploaded_ch \| 🍅_id` (one per line) |
| `UPDATE_CHAPTERS` | `🍅_id \| uploaded_ch` (one per line) |
| `MOVE_TO_UPLOADING` | `🍅_id \| 🟦_id` (one per line, 🟦 optional) |
| `DELETE_WAITING` | `🍅_id` (one per line) |
| `DELETE_UPLOADING` | `🍅_id` (one per line) |
