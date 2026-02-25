# sql-query-generation

To use this application add a .env file in the root level with the following key: `API_KEY={Add  OpenAI key here}`

Run the application with the command: `npx ts-node src/index.ts`

Database Analysis: Call the POST API:
`http://localhost:3000/api/database/analyze-database`

with the following DTO in the body:

```json
{
	"type": "postgres",
	"host": "{DatabaseHost}",
	"port": "{DatabasePort}",
	"username": "{DatabaseUserName}",
	"password": "{DatabasePassword}",
	"database": "{DatabaseName}",
	"schema": "{SchemaName}"
}
```

```json
{
	"type": "postgres",
	"host": "localhost",
	"port": "5432",
	"username": "myuser",
	"password": "mypass",
	"database": "fussballdb",
	"schema": "public"
}
```

Task Generation: Call the GET API:
`http://localhost:3000/api/generation/generate` with the following body:

```json
{
	"connectionInfo": {
		"type": "postgres",
		"host": "localhost",
		"port": "5432",
		"username": "myuser",
		"password": "mypass",
		"database": "fussballdb",
		"schema": "public"
	},
	"taskConfiguration": {
		"aggregation": false,
		"columnCount": 2,
		"predicateCount": 2,
		"operationTypes": [],
		"joinDepth": 2,
		"joinTypes": [],
		"groupby": false,
		"having": false,
		"orderby": true
	}
}
```

```json
{
	"connectionInfo": {
		"type": "postgres",
		"host": "localhost",
		"port": "5432",
		"username": "myuser",
		"password": "mypass",
		"database": "fussballdb",
		"schema": "public"
	},
	"taskConfiguration": {
		"aggregation": false,
		"columnCount": 2,
		"predicateCount": 2,
		"operationTypes": [],
		"joinDepth": 2,
		"joinTypes": [],
		"groupby": false,
		"having": false,
		"orderby": true
	}
}
```

What is possible to fill out in the configuration parameters can be found in interfaces.ts/ITaskConfiguration.

Grading: Call the POST API:
`http://localhost:3000/api/grading/grade`
with the following body:

```json
{
	"connectionInfo": {
		"type": "postgres",
		"host": "{DatabaseHost}",
		"port": "{DatabasePort}",
		"username": "{DatabaseUserName}",
		"password": "{DatabasePassword}",
		"database": "{DatabaseName}",
		"schema": "{SchemaName}"
	},
	"gradingRequest": {
		"taskId": "{Copy this value from the response of the task generation}",
		"studentQuery": "{Enter your query here}"
	}
}
```

```json
{
	"connectionInfo": {
		"type": "postgres",
		"host": "localhost",
		"port": "5432",
		"username": "myuser",
		"password": "mypass",
		"database": "fussballdb",
		"schema": "public"
	},
	"gradingRequest": {
		"taskId": "4f7c66ed-e4e5-422e-8d6f-ef4ee3876d07",
		"studentQuery": "SELECT character.kindid, character.genderid FROM public.couple INNER JOIN public.character ON couple.femaleid = character.characterid INNER JOIN public.kind ON character.kindid = kind.kindid WHERE kind.kindid >= 1 AND kind.kindid <= 4    OR character.characterid = 108 ORDER BY couple.femaleid ASC"
	}
}
```
