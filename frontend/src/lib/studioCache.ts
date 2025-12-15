export interface AudioBufferData {
  sampleRate: number;
  length: number;
  numberOfChannels: number;
  channels: Float32Array[];
}

export class StudioCache {
  private static DB_NAME = "piroola-studio-cache";
  private static STORE_NAME = "stems";
  private static VERSION = 1;

  private static dbPromise: Promise<IDBDatabase> | null = null;

  private static getDB(): Promise<IDBDatabase> {
    if (this.dbPromise) return this.dbPromise;

    this.dbPromise = new Promise((resolve, reject) => {
      if (typeof window === "undefined") {
        reject(new Error("IndexedDB not available server-side"));
        return;
      }

      const request = indexedDB.open(this.DB_NAME, this.VERSION);

      request.onupgradeneeded = (event) => {
        const db = (event.target as IDBOpenDBRequest).result;
        if (!db.objectStoreNames.contains(this.STORE_NAME)) {
          db.createObjectStore(this.STORE_NAME);
        }
      };

      request.onsuccess = (event) => {
        resolve((event.target as IDBOpenDBRequest).result);
      };

      request.onerror = (event) => {
        reject((event.target as IDBOpenDBRequest).error);
      };
    });

    return this.dbPromise;
  }

  static async getCachedArrayBuffer(key: string): Promise<ArrayBuffer | null> {
    try {
      const db = await this.getDB();
      return new Promise((resolve, reject) => {
        const transaction = db.transaction(this.STORE_NAME, "readonly");
        const store = transaction.objectStore(this.STORE_NAME);
        const request = store.get(key);

        request.onsuccess = () => {
          resolve(request.result || null);
        };
        request.onerror = () => {
          reject(request.error);
        };
      });
    } catch (e) {
      console.warn("StudioCache read error:", e);
      return null;
    }
  }

  static async cacheArrayBuffer(key: string, buffer: ArrayBuffer): Promise<void> {
    try {
      const db = await this.getDB();
      return new Promise((resolve, reject) => {
        const transaction = db.transaction(this.STORE_NAME, "readwrite");
        const store = transaction.objectStore(this.STORE_NAME);
        const request = store.put(buffer, key);

        request.onsuccess = () => {
          resolve();
        };
        request.onerror = () => {
          reject(request.error);
        };
      });
    } catch (e) {
      console.warn("StudioCache write error:", e);
    }
  }

  static async getAudioBufferData(key: string): Promise<AudioBufferData | null> {
    try {
      const db = await this.getDB();
      return new Promise((resolve, reject) => {
        const transaction = db.transaction(this.STORE_NAME, "readonly");
        const store = transaction.objectStore(this.STORE_NAME);
        const request = store.get(key);

        request.onsuccess = () => {
          const result = request.result;
          // Verify it matches the interface roughly
          if (result && typeof result.sampleRate === 'number' && Array.isArray(result.channels)) {
             resolve(result as AudioBufferData);
          } else {
             resolve(null);
          }
        };
        request.onerror = () => {
          reject(request.error);
        };
      });
    } catch (e) {
      console.warn("StudioCache read error:", e);
      return null;
    }
  }

  static async cacheAudioBufferData(key: string, data: AudioBufferData): Promise<void> {
    try {
      const db = await this.getDB();
      return new Promise((resolve, reject) => {
        const transaction = db.transaction(this.STORE_NAME, "readwrite");
        const store = transaction.objectStore(this.STORE_NAME);
        const request = store.put(data, key);

        request.onsuccess = () => {
          resolve();
        };
        request.onerror = () => {
          reject(request.error);
        };
      });
    } catch (e) {
      console.warn("StudioCache write error:", e);
    }
  }
}
