const fs = require('fs');
const path = require('path');

export function deleteFolder(dirPath) {
    if (fs.existsSync(dirPath)) {
        fs.rmSync(dirPath, { recursive: true, force: true });
        console.log(`Deleted: ${dirPath}`);
    } else {
        console.log(`Folder not found: ${dirPath}`);
    }
}
