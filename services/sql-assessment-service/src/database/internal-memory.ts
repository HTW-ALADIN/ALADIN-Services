import type { PGlite } from '@electric-sql/pglite';
import { IParsedTable } from '../shared/interfaces/domain';

export const databaseMetadata: Map<string, IParsedTable[]> = new Map();

export const selfJoinDatabaseMetadata: Map<string, IParsedTable[]> = new Map();

// Stores live PGlite instances indexed by databaseId.

export const pgliteInstances: Map<string, PGlite> = new Map();
