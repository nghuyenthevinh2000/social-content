const DRAFT_STORAGE_KEY = 'aibrand-video-edit-draft';
const IDB_NAME = 'aibrand-video-edit-db';
const IDB_STORE = 'files';
const IDB_KEY = 'source';

export type VideoEditDraft = {
  prompt: string;
  referenceUrl: string;
  historyJobId: string | null;
};

export function loadEditDraft(): VideoEditDraft {
  try {
    const raw = localStorage.getItem(DRAFT_STORAGE_KEY);
    if (!raw) return { prompt: '', referenceUrl: '', historyJobId: null };
    const parsed = JSON.parse(raw);
    return {
      prompt: typeof parsed?.prompt === 'string' ? parsed.prompt : '',
      referenceUrl: typeof parsed?.referenceUrl === 'string' ? parsed.referenceUrl : '',
      historyJobId: typeof parsed?.historyJobId === 'string' ? parsed.historyJobId : null,
    };
  } catch {
    return { prompt: '', referenceUrl: '', historyJobId: null };
  }
}

export function saveEditDraft(draft: VideoEditDraft): void {
  try {
    localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(draft));
  } catch {
    // ignore storage quota / privacy mode errors
  }
}

function openVideoDb(): Promise<IDBDatabase | null> {
  if (typeof indexedDB === 'undefined') return Promise.resolve(null);
  return new Promise((resolve) => {
    try {
      const req = indexedDB.open(IDB_NAME, 1);
      req.onupgradeneeded = () => {
        if (!req.result.objectStoreNames.contains(IDB_STORE)) {
          req.result.createObjectStore(IDB_STORE);
        }
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => resolve(null);
    } catch {
      resolve(null);
    }
  });
}

export async function loadEditVideoFile(): Promise<File | null> {
  const db = await openVideoDb();
  if (!db) return null;
  return new Promise((resolve) => {
    try {
      const tx = db.transaction(IDB_STORE, 'readonly');
      const req = tx.objectStore(IDB_STORE).get(IDB_KEY);
      req.onsuccess = () => {
        const val = req.result;
        resolve(val instanceof File ? val : null);
      };
      req.onerror = () => resolve(null);
      tx.oncomplete = () => db.close();
    } catch {
      db.close();
      resolve(null);
    }
  });
}

export async function saveEditVideoFile(file: File | null): Promise<void> {
  const db = await openVideoDb();
  if (!db) return;
  return new Promise((resolve) => {
    try {
      const tx = db.transaction(IDB_STORE, 'readwrite');
      const store = tx.objectStore(IDB_STORE);
      if (file) {
        store.put(file, IDB_KEY);
      } else {
        store.delete(IDB_KEY);
      }
      tx.oncomplete = () => {
        db.close();
        resolve();
      };
      tx.onerror = () => {
        db.close();
        resolve();
      };
    } catch {
      db.close();
      resolve();
    }
  });
}

export function clearEditDraft(): void {
  try {
    localStorage.removeItem(DRAFT_STORAGE_KEY);
  } catch {
    // ignore
  }
  void saveEditVideoFile(null);
}
