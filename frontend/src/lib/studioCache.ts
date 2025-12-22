
import { openDB, DBSchema, IDBPDatabase } from 'idb';

export interface AudioBufferData {
  sampleRate: number;
  length: number;
  duration: number;
  numberOfChannels: number;
  channels: Float32Array[];
}

interface StudioDB extends DBSchema {
  audio_buffers: {
    key: string;
    value: {
      fileName: string;
      data: AudioBufferData;
      timestamp: number;
    };
    indexes: { 'by-filename': string };
  };
}

export class StudioCache {
  private dbPromise: Promise<IDBPDatabase<StudioDB>> | null = null;

  private getDB() {
    if (typeof window === 'undefined') return null;
    if (!this.dbPromise) {
      this.dbPromise = openDB<StudioDB>('piroola-studio-cache', 1, {
        upgrade(db) {
          const store = db.createObjectStore('audio_buffers', { keyPath: 'fileName' });
          store.createIndex('by-filename', 'fileName');
        },
      });
    }
    return this.dbPromise;
  }

  async getAudioBuffer(fileName: string): Promise<AudioBufferData | undefined> {
    const db = this.getDB();
    if (!db) return undefined;
    const result = await (await db).get('audio_buffers', fileName);
    return result?.data;
  }

  async setAudioBuffer(fileName: string, data: AudioBufferData): Promise<void> {
    const db = this.getDB();
    if (!db) return;
    await (await db).put('audio_buffers', {
      fileName,
      data,
      timestamp: Date.now(),
    });
  }

  async clear(): Promise<void> {
    const db = this.getDB();
    if (!db) return;
    await (await db).clear('audio_buffers');
  }
}

export const studioCache = new StudioCache();
