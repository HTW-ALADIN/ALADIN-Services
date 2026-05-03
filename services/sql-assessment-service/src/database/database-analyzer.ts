import { DataSource, Table } from 'typeorm';
import 'reflect-metadata';
import {
	IParsedColumn,
	IParsedTable,
	IJoinPaths,
	IPath,
	IAliasMap,
	EntityType,
	RelationshipType,
	Participation,
	IForeignKeyRelationship,
} from '../shared/interfaces/domain';
import { databaseMetadata, selfJoinDatabaseMetadata } from './internal-memory';

export class DatabaseAnalyzer {
	public async extractDatabaseSchema(
		dataSource: DataSource,
		schema: string,
		databaseKey: string,
		aliasMap?: IAliasMap,
	): Promise<boolean> {
		try {
			const queryRunner = dataSource.createQueryRunner();
			const tables: Table[] = await queryRunner.getTables();
			await queryRunner.release();

			const filteredTables = tables.filter((table) => table.schema === schema);
			return this.buildAndStoreParsedTables(
				filteredTables,
				schema,
				databaseKey,
				aliasMap,
			);
		} catch (error: any) {
			console.log('Unable to parse database schema', error);
			return false;
		}
	}

	/**
	 * Analyzes the schema of an in-process PGlite database using
	 * `information_schema` SQL queries and stores the result in the same
	 * in-memory registry used by the PostgreSQL path.
	 *
	 * @param db  - A live PGlite instance that has already been initialised
	 *             with the desired DDL.
	 * @param key - The registry key under which metadata is stored (use
	 *              `generatePGliteKey(databaseId)`).
	 * @param aliasMap - Optional human-readable alias map.
	 */
	public async extractSchemaFromPGlite(
		db: any,
		key: string,
		aliasMap?: IAliasMap,
	): Promise<boolean> {
		try {
			const schema = 'public';

			// --- Discover tables in the public schema ---
			const tablesRes = await db.query(
				`SELECT table_name FROM information_schema.tables
				 WHERE table_schema = $1 AND table_type = 'BASE TABLE'
				 ORDER BY table_name`,
				[schema],
			);
			const tableNames: string[] = tablesRes.rows.map((r: any) => r.table_name);

			if (tableNames.length === 0) return false;

			// --- Build a synthetic Table-like array from information_schema ---
			const syntheticTables: Table[] = [];

			for (const tableName of tableNames) {
				const colRes = await db.query(
					`SELECT column_name, data_type, is_nullable
					 FROM information_schema.columns
					 WHERE table_schema = $1 AND table_name = $2
					 ORDER BY ordinal_position`,
					[schema, tableName],
				);

				const pkRes = await db.query(
					`SELECT kcu.column_name
					 FROM information_schema.table_constraints tc
					 JOIN information_schema.key_column_usage kcu
					   ON tc.constraint_name = kcu.constraint_name
					   AND tc.table_schema = kcu.table_schema
					 WHERE tc.constraint_type = 'PRIMARY KEY'
					   AND tc.table_schema = $1 AND tc.table_name = $2
					 ORDER BY kcu.ordinal_position`,
					[schema, tableName],
				);

				const fkRes = await db.query(
					`SELECT kcu.column_name, ccu.table_name AS referenced_table,
					        ccu.column_name AS referenced_column
					 FROM information_schema.table_constraints tc
					 JOIN information_schema.key_column_usage kcu
					   ON tc.constraint_name = kcu.constraint_name
					   AND tc.table_schema = kcu.table_schema
					 JOIN information_schema.constraint_column_usage ccu
					   ON ccu.constraint_name = tc.constraint_name
					   AND ccu.constraint_schema = tc.constraint_schema
					 WHERE tc.constraint_type = 'FOREIGN KEY'
					   AND tc.table_schema = $1 AND tc.table_name = $2
					 ORDER BY kcu.ordinal_position`,
					[schema, tableName],
				);

				const uqRes = await db.query(
					`SELECT tc.constraint_name, kcu.column_name
					 FROM information_schema.table_constraints tc
					 JOIN information_schema.key_column_usage kcu
					   ON tc.constraint_name = kcu.constraint_name
					   AND tc.table_schema = kcu.table_schema
					 WHERE tc.constraint_type = 'UNIQUE'
					   AND tc.table_schema = $1 AND tc.table_name = $2
					 ORDER BY tc.constraint_name, kcu.ordinal_position`,
					[schema, tableName],
				);

				// Group columns by constraint name so that composite UNIQUE constraints
				// are represented as a single entry with multiple columnNames, matching
				// the shape TypeORM returns for the real-DB path.
				const uqGroups = new Map<string, string[]>();
				for (const r of uqRes.rows as Array<{
					constraint_name: string;
					column_name: string;
				}>) {
					const cols = uqGroups.get(r.constraint_name) ?? [];
					cols.push(r.column_name);
					uqGroups.set(r.constraint_name, cols);
				}

				// Query unique indices from pg_catalog so that explicit
				// CREATE UNIQUE INDEX statements are also captured.  Primary-key
				// indices are excluded because they are handled via primaryColumns.
				// Results are ordered by attnum so that composite index column order
				// is preserved.
				const idxRes = await db.query(
					`SELECT i.relname AS index_name, a.attname AS column_name
					 FROM pg_class t
					 JOIN pg_namespace n ON n.oid = t.relnamespace
					 JOIN pg_index ix ON t.oid = ix.indrelid
					 JOIN pg_class i ON i.oid = ix.indexrelid
					 JOIN pg_attribute a
					   ON a.attrelid = t.oid AND a.attnum = ANY(ix.indkey)
					 WHERE n.nspname = $1 AND t.relname = $2
					   AND ix.indisunique = true AND NOT ix.indisprimary
					 ORDER BY i.relname, a.attnum`,
					[schema, tableName],
				);

				// Group per index name (composite indices → multiple columns).
				const idxGroups = new Map<string, string[]>();
				for (const r of idxRes.rows as Array<{
					index_name: string;
					column_name: string;
				}>) {
					const cols = idxGroups.get(r.index_name) ?? [];
					cols.push(r.column_name);
					idxGroups.set(r.index_name, cols);
				}

				// Cast as unknown as Table so the existing private helpers
				// (which type-check against TypeORM's Table) can be reused.
				// At runtime only the properties accessed by those helpers need
				// to be present, and they are all provided below.
				syntheticTables.push({
					name: `${schema}.${tableName}`,
					schema,
					columns: colRes.rows.map((r: any) => ({
						name: r.column_name,
						type: r.data_type,
						isNullable: r.is_nullable === 'YES',
					})),
					primaryColumns: pkRes.rows.map((r: any) => ({ name: r.column_name })),
					foreignKeys: fkRes.rows.map((r: any) => ({
						columnNames: [r.column_name],
						referencedTableName: r.referenced_table,
						referencedColumnNames: [r.referenced_column],
					})),
					uniques: [...uqGroups.values()].map((columnNames) => ({
						columnNames,
					})),
					indices: [...idxGroups.entries()].map(([name, columnNames]) => ({
						name,
						columnNames,
						isUnique: true,
					})),
				} as unknown as Table);
			}

			return this.buildAndStoreParsedTables(
				syntheticTables,
				schema,
				key,
				aliasMap,
			);
		} catch (error: any) {
			console.log('Unable to parse PGlite database schema', error);
			return false;
		}
	}

	// -------------------------------------------------------------------------
	// Shared schema processing
	// -------------------------------------------------------------------------

	/**
	 * Builds `IParsedTable[]` from an already-filtered array of raw Table
	 * objects (either real TypeORM Tables or synthetic objects from PGlite),
	 * runs entity-type classification and N:M propagation, then stores the
	 * results in the in-memory registry.
	 */
	private buildAndStoreParsedTables(
		filteredTables: Table[],
		schema: string,
		key: string,
		aliasMap?: IAliasMap,
	): boolean {
		if (filteredTables.length === 0) return false;

		// ----------------------------------------------------------------
		// First pass: build base IParsedTable entries (columns + join paths)
		// ----------------------------------------------------------------
		const parsedTables: IParsedTable[] = [];
		const selfJoinTable: IParsedTable[] = [];

		filteredTables.forEach((table) => {
			const tableName = this.getTableName(table.name);

			// --- Collect PK column names for this table ---
			const pkColumnNames = new Set<string>(
				table.primaryColumns.map((pc) => pc.name),
			);

			// --- Collect FK column names for this table ---
			const fkColumnNames = new Set<string>(
				table.foreignKeys.flatMap((fk) => fk.columnNames),
			);

			// --- Collect unique-indexed column names (used for 1:1 detection) ---
			// Only single-column UNIQUE constraints make a column individually unique.
			// A composite UNIQUE(col_a, col_b) must NOT mark col_a or col_b as unique
			// on their own, otherwise buildRelationships() would misclassify 1:N FKs
			// as 1:1.
			const uniqueColumnNames = new Set<string>(
				table.uniques
					.filter((u) => u.columnNames.length === 1)
					.map((u) => u.columnNames[0]),
			);

			// --- Build parsed columns ---
			const parsedColumns: IParsedColumn[] = table.columns.map((column) => ({
				name: column.name,
				tableName: tableName,
				type: column.type,
				isNullable: column.isNullable,
				isPrimaryKey: pkColumnNames.has(column.name),
				isForeignKey: fkColumnNames.has(column.name),
				alternativeName: aliasMap?.columns?.[tableName]?.[column.name],
			}));

			// --- Build FK relationships ---
			const relationships = this.buildRelationships(
				table,
				tableName,
				pkColumnNames,
				uniqueColumnNames,
			);

			// --- Build join paths ---
			const joinPaths = this.findJoinPaths(
				tableName,
				[],
				0,
				new Set(),
				filteredTables,
				schema,
				false,
			);

			const [selfJoinPaths, otherPaths] =
				this.separateSelfAndNonSelfJoinPaths(joinPaths);

			const baseEntry: Omit<
				IParsedTable,
				| 'entityType'
				| 'relationships'
				| 'supertableOf'
				| 'subtableOf'
				| 'alternativeName'
			> = {
				name: tableName,
				joinPaths: [], // filled below
				columns: parsedColumns,
			};

			parsedTables.push({
				...baseEntry,
				joinPaths: this.filterJoinPaths(tableName, otherPaths),
				// Placeholder values — overwritten in second pass
				entityType: EntityType.Strong,
				relationships,
				alternativeName: aliasMap?.tables?.[tableName],
			});

			selfJoinTable.push({
				...baseEntry,
				joinPaths: this.filterJoinPaths(tableName, selfJoinPaths),
				entityType: EntityType.Strong,
				relationships,
				alternativeName: aliasMap?.tables?.[tableName],
			});
		});

		// ----------------------------------------------------------------
		// Second pass: classify entity types and wire supertype/subtype
		// ----------------------------------------------------------------
		this.classifyEntities(parsedTables, filteredTables, schema);
		this.classifyEntities(selfJoinTable, filteredTables, schema);

		// Propagate N:M cardinality onto the two tables bridged by each
		// associative table.
		this.propagateManyToMany(parsedTables);
		this.propagateManyToMany(selfJoinTable);

		databaseMetadata.set(key, parsedTables);
		selfJoinDatabaseMetadata.set(key, selfJoinTable);
		return true;
	}

	// -------------------------------------------------------------------------
	// Entity-type classification
	// -------------------------------------------------------------------------

	/**
	 * Classifies each table's EntityType and wires supertype/subtype links.
	 * Operates in-place on the provided array.
	 */
	private classifyEntities(
		parsedTables: IParsedTable[],
		rawTables: Table[],
		schema: string,
	): void {
		// Build a quick lookup: tableName → rawTable
		const rawMap = new Map<string, Table>();
		rawTables.forEach((t) => rawMap.set(this.getTableName(t.name), t));

		// Build a lookup for PK column sets per table (raw names)
		const pkMap = new Map<string, Set<string>>();
		rawTables.forEach((t) => {
			pkMap.set(
				this.getTableName(t.name),
				new Set(t.primaryColumns.map((c) => c.name)),
			);
		});

		// ---- Classify each table ----
		for (const parsedTable of parsedTables) {
			const raw = rawMap.get(parsedTable.name);
			if (!raw) continue;

			const pkCols = pkMap.get(parsedTable.name) ?? new Set<string>();
			const fkColNames = new Set<string>(
				raw.foreignKeys.flatMap((fk) => fk.columnNames),
			);
			const referencedTables = raw.foreignKeys.map((fk) =>
				this.getTableName(fk.referencedTableName),
			);

			// Associative: every PK column is also a FK column
			const allPkAreFk =
				pkCols.size > 0 && [...pkCols].every((col) => fkColNames.has(col));

			// Subtype: the table has exactly one FK that references another table
			//          AND that FK column set equals the full PK of this table
			//          (shared-PK pattern → IS-A relationship).
			const isSubtype = this.detectSubtype(raw, pkCols, pkMap, schema);

			// Weak: at least one PK column is a FK, but not all (partial dependency)
			const somePkAreFk =
				pkCols.size > 0 && [...pkCols].some((col) => fkColNames.has(col));

			if (allPkAreFk && referencedTables.length >= 2) {
				parsedTable.entityType = EntityType.Associative;
			} else if (isSubtype) {
				parsedTable.entityType = EntityType.Subtype;
			} else if (somePkAreFk) {
				parsedTable.entityType = EntityType.Weak;
			} else {
				parsedTable.entityType = EntityType.Strong;
			}
		}

		// ---- Back-fill supertype ↔ subtype links ----
		const tableMap = new Map<string, IParsedTable>(
			parsedTables.map((t) => [t.name, t]),
		);

		for (const parsedTable of parsedTables) {
			if (parsedTable.entityType !== EntityType.Subtype) continue;

			const raw = rawMap.get(parsedTable.name);
			if (!raw) continue;

			const pkCols = pkMap.get(parsedTable.name) ?? new Set<string>();

			// Find the FK whose column set equals the full PK of this table
			for (const fk of raw.foreignKeys) {
				// const fkCols = new Set<string>(fk.columnNames);
				const sharedWithPk = fk.columnNames.every((c) => pkCols.has(c));
				if (!sharedWithPk) continue;

				const supertableName = this.getTableName(fk.referencedTableName);
				parsedTable.subtableOf = supertableName;

				const superEntry = tableMap.get(supertableName);
				if (superEntry) {
					if (!superEntry.supertableOf) superEntry.supertableOf = [];
					if (!superEntry.supertableOf.includes(parsedTable.name)) {
						superEntry.supertableOf.push(parsedTable.name);
					}
				}
				break; // Only one supertype per table
			}
		}
	}

	/**
	 * Returns true when the table uses a shared-PK pattern:
	 * the table's full PK is covered by FK columns that reference another table's PK.
	 */
	private detectSubtype(
		table: Table,
		pkCols: Set<string>,
		pkMap: Map<string, Set<string>>,
		_schema: string,
	): boolean {
		if (pkCols.size === 0) return false;

		for (const fk of table.foreignKeys) {
			const refTableName = this.getTableName(fk.referencedTableName);
			const refPkCols = pkMap.get(refTableName);
			if (!refPkCols) continue;

			// All PK columns of this table must be covered by this FK's columns
			const fkColSet = new Set<string>(fk.columnNames);
			const allPkCoveredByFk = [...pkCols].every((c) => fkColSet.has(c));

			// The referenced columns must be the PK of the referenced table
			const fkRefColSet = new Set<string>(fk.referencedColumnNames);
			const referencesFullPk = [...refPkCols].every((c) => fkRefColSet.has(c));

			if (allPkCoveredByFk && referencesFullPk) return true;
		}
		return false;
	}

	// -------------------------------------------------------------------------
	// Relationship building
	// -------------------------------------------------------------------------

	private buildRelationships(
		table: Table,
		tableName: string,
		pkColumnNames: Set<string>,
		uniqueColumnNames: Set<string>,
	): IForeignKeyRelationship[] {
		return table.foreignKeys.map((fk) => {
			const fkCol = fk.columnNames[0];
			const referencedTable = this.getTableName(fk.referencedTableName);
			const referencedColumn = fk.referencedColumnNames[0];

			const isIdentifying = fk.columnNames.every((c) => pkColumnNames.has(c));

			// Find the actual column definition to check nullability
			const columnDef = table.columns.find((c) => c.name === fkCol);
			const participation = columnDef?.isNullable
				? Participation.Optional
				: Participation.Mandatory;

			// 1:1 if the FK column has a unique constraint or unique index that covers
			// exactly that one column. Composite unique constraints / indices must not
			// qualify, because UNIQUE(a, b) does not mean column a is individually unique.
			const hasUniqueConstraint =
				uniqueColumnNames.has(fkCol) ||
				table.indices.some(
					(idx) =>
						idx.isUnique &&
						idx.columnNames.length === 1 &&
						idx.columnNames[0] === fkCol,
				);

			// N:M is assigned later by propagateManyToMany; default to 1:N here
			const cardinality = hasUniqueConstraint
				? RelationshipType.OneToOne
				: RelationshipType.OneToMany;

			return {
				fkColumn: fkCol,
				referencedTable,
				referencedColumn,
				isIdentifying,
				participation,
				cardinality,
			};
		});
	}

	// -------------------------------------------------------------------------
	// N:M propagation via associative tables
	// -------------------------------------------------------------------------

	/**
	 * For every associative (junction) table, marks the FK relationships on
	 * the two bridged tables as N:M.
	 */
	private propagateManyToMany(parsedTables: IParsedTable[]): void {
		const tableMap = new Map<string, IParsedTable>(
			parsedTables.map((t) => [t.name, t]),
		);

		for (const table of parsedTables) {
			if (table.entityType !== EntityType.Associative) continue;
			if (table.relationships.length < 2) continue;

			const bridgedTables = table.relationships.map((r) => r.referencedTable);

			// Mark relationship on each bridged side
			for (let i = 0; i < bridgedTables.length; i++) {
				const sideA = tableMap.get(bridgedTables[i]);
				if (!sideA) continue;

				// For each other bridged table
				for (let j = 0; j < bridgedTables.length; j++) {
					if (i === j) continue;
					// Find the FK relationship on sideA that points to the junction table
					// (sideA itself usually doesn't hold the FK; the junction table does).
					// We instead mark the relationship on the junction entry towards sideA's peer.
					// Update the junction table's FK relationships to N:M
					for (const rel of table.relationships) {
						rel.cardinality = RelationshipType.ManyToMany;
					}
				}
			}
		}
	}

	// -------------------------------------------------------------------------
	// Existing join-path helpers (unchanged)
	// -------------------------------------------------------------------------

	private findJoinPaths(
		tableName: string,
		path: IPath[],
		depth: number,
		visited: Set<string>,
		tables: Table[],
		schema: string,
		isPreviousPathSelfJoin: boolean,
	): IJoinPaths[] {
		const results: IJoinPaths[] = [];
		const visitedPaths = new Set(visited);

		const table = tables.find(
			(table) =>
				table.name === `${schema}.${tableName}` || table.name === tableName,
		);

		if (!table) return results;

		const relatedTables = table.foreignKeys.map((fk) => ({
			tableName: this.getTableName(fk.referencedTableName),
			relationKey: `${this.getTableName(table.name)}.${fk.columnNames[0]} = ${this.getTableName(fk.referencedTableName)}.${fk.referencedColumnNames[0]}`,
		}));

		for (const relation of relatedTables) {
			const newPath: IPath[] = [
				...path,
				{ tableName: relation.tableName, relationKey: relation.relationKey },
			];
			const pathKey = `${tableName}-${relation.relationKey}-${relation.tableName}`;

			if (visitedPaths.has(pathKey)) continue;
			visitedPaths.add(pathKey);

			const newDepth = depth + 1;
			const isSelfJoin =
				isPreviousPathSelfJoin || tableName === relation.tableName;

			results.push({
				path: newPath,
				depth: newDepth,
				isSelfJoin: isSelfJoin,
				selfJoinDepth: 0,
			});

			const recursivePaths = this.findJoinPaths(
				relation.tableName,
				newPath,
				newDepth,
				new Set(visitedPaths),
				tables,
				schema,
				isSelfJoin,
			);

			results.push(...recursivePaths);
		}

		return results;
	}

	private separateSelfAndNonSelfJoinPaths(
		paths: IJoinPaths[],
	): [selfPaths: IJoinPaths[], otherPaths: IJoinPaths[]] {
		const selfPaths = paths.filter((path) => path.isSelfJoin);
		const otherPaths = paths.filter((path) => !path.isSelfJoin);
		return [selfPaths, otherPaths];
	}

	private filterJoinPaths(
		currentTableName: string,
		paths: IJoinPaths[],
	): IJoinPaths[] {
		const uniquePaths = new Map<string, IJoinPaths>();

		for (const path of paths) {
			const key = path.path.map((p) => p.tableName).join('->');

			let selfJoinDepth: number = 0;
			if (path.isSelfJoin) {
				const tableNames = new Set<string>();
				for (let i = 0; i < path.path.length; i++) {
					const tableName = path.path[i].tableName;

					if (currentTableName === tableName) {
						selfJoinDepth = i + 1;
					}
					if (tableNames.has(tableName)) {
						selfJoinDepth = i + 1;
					} else {
						tableNames.add(tableName);
					}
				}
			}
			const pathWithSelfJoinDepth: IJoinPaths = {
				...path,
				selfJoinDepth: selfJoinDepth,
			};

			const existingPath = uniquePaths.get(key);
			if (!existingPath || existingPath.depth < path.depth) {
				uniquePaths.set(key, pathWithSelfJoinDepth);
			}
		}

		const sortedPaths = Array.from(uniquePaths.values()).sort(
			(a, b) => b.depth - a.depth,
		);

		const finalPaths: IJoinPaths[] = [];
		const seenKeys = new Set<string>();

		for (const path of sortedPaths) {
			const key = path.path.map((p) => p.tableName).join('->');

			let isSubPath = false;
			for (const existingKey of seenKeys) {
				if (existingKey.startsWith(key)) {
					isSubPath = true;
					break;
				}
			}

			if (!isSubPath) {
				finalPaths.push(path);
				seenKeys.add(key);
			}
		}

		return finalPaths;
	}

	private getTableName(tableName: string): string {
		const names = tableName.split('.');
		return names.length > 1 ? names[1] : names[0];
	}
}
