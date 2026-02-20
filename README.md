## Usage

### Waiting List
Add books you're waiting on (paste in bulk):
```
Vietnamese Title | Desired Chapters | 🍅 Book ID
```
Books with a ✓ READY badge have hit the desired chapter count. Select them and click **→ Move to Uploading**.

### Uploading List
Add books you're already uploading (paste in bulk):
```
🟦 Book ID | Uploaded Chapters | 🍅 Book ID
```
Select multiple books and click **✏️ Update Chapters** — the panel stays pinned so you can switch to 🟦CV and look up the number.

---

## Issue Commands 

You can also manage data by creating issues with these titles:

| Issue Title | Body Format |
|---|---|
| `ADD_WAITING` | `Vi Title \| desired_ch \| 🍅_id` (one per line) |
| `ADD_UPLOADING` | `🟦_id \| uploaded_ch \| 🍅_id` (one per line) |
| `UPDATE_CHAPTERS` | `🍅_id \| uploaded_ch` (one per line) |
| `MOVE_TO_UPLOADING` | `🍅_id \| 🟦_id` (one per line, 🟦 optional) |
| `DELETE_WAITING` | `🍅_id` (one per line) |
| `DELETE_UPLOADING` | `🍅_id` (one per line) |

Issues are auto-closed after processing.
