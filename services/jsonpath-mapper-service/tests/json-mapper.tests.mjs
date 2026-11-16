import { expect } from 'chai';
import { JSONPath } from 'jsonpath-plus';
import { createRequire } from 'node:module';
import {
  store,
  nullSearchPayload,
  queryParamsToCourseApi,
  getQuery,
} from './sample-data.mjs';
import * as m from './mappers/index.mjs';
import * as a from './acceptance/index.mjs';
import { siteConfigEntry } from './sample-data.mjs';
import { mapArrayObject } from './sample-data.mjs';

const { default: mapJson, mapJsonAsync, jpath } = await import(
  process.env.MAPPER_COVERAGE ? '../src/index.ts' : 'jsonpath-mapper'
);

console.log('mapJson: ', mapJson);
console.log('mapJsonAsync: ', mapJsonAsync);

let count = 0;

/* eslint-disable no-unused-vars */
const logData = (data) => console.log('\ntest data: \n', data);
const logTemplate = (template) => console.log('template: \n', template);
const logResult = (result) => console.log('\nresult: \n', result, '\n');
const logTest = (testName, testNum) =>
  console.log(
    '\n===============================\n\n',
    'Test',
    testNum ? `${testNum}: ${testName}` : testName,
    '\n----------------\n'
  );

const doTest = (data, testName, mapper, key) => {
  let result = {};
  let asyncResult = {};
  let testNum = 0;
  // eslint-disable-next-line mocha/no-top-level-hooks
  before(async () => {
    testNum = count += 1;
    result = mapJson(data, m[mapper]);
    asyncResult = await mapJsonAsync(data, m[mapper]);
  });
  it(testName, () => {
    expect(key ? result[key] : result).to.deep.equal(
      key ? a[mapper][key] : a[mapper]
    );
  });
  it(`${testName} (async)`, () => {
    expect(key ? asyncResult[key] : asyncResult).to.deep.equal(
      key ? a[mapper][key] : a[mapper]
    );
  });
  // after(() => {
  //   logTest(testName, testNum);
  //   logTemplate(key ? m[mapper][key] : m[mapper]);
  //   logResult(key ? result[key] : result);
  // });
};

// Testing the tests
describe('First test', () => {
  it('Test the tests: Should assert true to be true', () => {
    expect(true).to.be.true;
  });
});

// Basic mapper template JSONPath expressions
describe('JSONPath tests', () => {
  doTest(store, 'Find all author objects', 'jsonPathTests', 'allBooksAuthors');
  doTest(
    store,
    'Find all author names',
    'jsonPathTests',
    'allBooksAuthorNames'
  );
  doTest(store, 'Find all names in books', 'jsonPathTests', 'allNamesInBooks');
  doTest(store, 'Find all author names', 'jsonPathTests', 'allAuthorNames');
  doTest(
    store,
    'Find all book titles by author name',
    'jsonPathTests',
    'allBookTitlesByAuthorName'
  );
  doTest(
    store,
    'Find all book titles by price less than 20',
    'jsonPathTests',
    'allBookTitlesByPriceLessThan'
  );
  doTest(store, 'Find first book title', 'jsonPathTests', 'firstBookTitle');
  doTest(store, 'Find last book title', 'jsonPathTests', 'lastBookTitle');
  doTest(
    store,
    'Find two first book titles',
    'jsonPathTests',
    'firstTwoBookTitles'
  );
  doTest(
    store,
    'Find two last book titles',
    'jsonPathTests',
    'lastTwoBookTitles'
  );
  doTest(
    store,
    'Find two book titles from second position',
    'jsonPathTests',
    'twoBookTitlesFromSecondPosition'
  );
  doTest(
    store,
    'long subpaths: find books by various authors, for under $20',
    'jsonPathTests',
    'booksByVariousAuthorWithPriceLessThan'
  );
  doTest(
    store,
    'nested predicates: same query, however ".author.name" isn\'t repeated. For JSON with many levels, enables much more compact queries.',
    'jsonPathTests',
    'booksByVariousAuthor'
  );
});

describe('JSONPath security', () => {
  const marker = '__jsonpathMapperCVE20251302__';
  const payload = `p="globalThis.${marker}=true";a=''[['constructor']][['constructor']](p);a()`;
  const queries = [
    ['filter', `..[?(${payload})]`],
    ['dynamic selector', `items[(${payload})]`],
  ];
  const data = { a: 1, items: [{ a: 1 }] };

  afterEach(() => {
    delete globalThis[marker];
  });

  it('disables evaluation for ordinary paths and uses safe evaluation for expressions', () => {
    const cjsJSONPath = createRequire(import.meta.url)('jsonpath-plus').JSONPath;
    const prototypes = [...new Set([JSONPath.prototype, cjsJSONPath.prototype])];
    const originalEvaluators = prototypes.map((prototype) => prototype.evaluate);
    const modes = [];
    const input = {
      items: [{ name: 'low', price: 5 }, { name: 'high', price: 25 }],
      quoted: { 'with(paren)': 42 },
    };
    try {
      prototypes.forEach((prototype, index) => {
        prototype.evaluate = function (...args) {
          modes.push(this.eval);
          return originalEvaluators[index].apply(this, args);
        };
      });
      expect(jpath('items[*].name', input)).to.deep.equal(['low', 'high']);
      expect(jpath("quoted['with(paren)']", input)).to.deep.equal([42]);
      expect(jpath('items[0,1].name', input)).to.deep.equal(['low', 'high']);
      expect(jpath('items[*].name.@string()', input)).to.deep.equal(['low', 'high']);
      expect(jpath('items[?(@.price < 20)].name', input)).to.deep.equal(['low']);
      expect(jpath('items[(@.length-1)].name', input)).to.deep.equal(['high']);
      expect(jpath('items[0,(@.length-1)].name', input)).to.deep.equal(['low', 'high']);
      expect(modes).to.deep.equal([false, false, false, false, 'safe', 'safe', 'safe']);
    } finally {
      prototypes.forEach((prototype, index) => {
        prototype.evaluate = originalEvaluators[index];
      });
    }
  });

  for (const [selector, query] of queries) {
    for (const [name, run] of [
      ['jpath', () => jpath(query, data)],
      ['sync mapper', () => mapJson(data, { value: query })],
      ['async mapper', () => mapJsonAsync(data, { value: query })],
      ['sync $path', () => mapJson(data, { value: { $path: query } })],
      ['async $path', () => mapJsonAsync(data, { value: { $path: query } })],
      ['sync fallback', () => mapJson(data, { value: ['missing', query] })],
      ['async fallback', () => mapJsonAsync(data, { value: ['missing', query] })],
    ]) {
      it(`blocks CVE-2025-1302 in a ${selector} without executing code in ${name}`, async () => {
        let error;
        try {
          await run();
        } catch (caught) {
          error = caught;
        }
        expect(globalThis[marker]).to.be.undefined;
        expect(error).to.be.instanceOf(Error);
      });
    }
  }
});

describe('Fallback values', () => {
  const data = { disabled: false, empty: '', zero: 0, present: 'present', missing: null };

  for (const [name, mapper] of [['sync', mapJson], ['async', mapJsonAsync]]) {
    it(`preserves falsy values in string fallbacks (${name})`, async () => {
      const template = {
        disabled: ['missing', 'disabled', 'present'],
        empty: ['absent', 'empty', 'present'],
        zero: ['absent', 'zero', 'present'],
        none: ['missing', 'absent'],
        path: { $path: ['absent', 'disabled', 'present'], $default: 'default' },
      };
      expect(await mapper(data, template)).to.deep.equal({
        disabled: false,
        empty: '',
        zero: 0,
        path: false,
      });
    });

    it(`preserves falsy values in mixed and nested fallbacks (${name})`, async () => {
      const template = {
        values: [
          () => null,
          () => undefined,
          () => false,
          () => '',
          () => 0,
          () => NaN,
          ['absent', 'empty', 'present'],
          { $path: ['absent', 'disabled', 'present'] },
        ],
      };
      expect(await mapper(data, template)).to.deep.equal({
        values: [false, '', 0, NaN, '', false],
      });
    });
  }

  it('preserves asynchronously resolved falsy values', async () => {
    const result = await mapJsonAsync(data, {
      values: [async () => null, async () => false, async () => '', async () => undefined],
    });
    expect(result).to.deep.equal({ values: [false, ''] });
  });
});

// Mapper feature tests
describe('Multiple paths with $path and $return hooks', () => {
  doTest(store, 'All prices for products in store', 'allPrices');
  doTest(nullSearchPayload, 'Dealing with a null payload', 'nullSearchPayload');
  doTest(
    mapArrayObject,
    'Mapping an object that is an array',
    'mapArrayObject'
  );
  doTest(
    queryParamsToCourseApi,
    'Converting query params to an api request',
    'disableEmptyParams'
  );
  doTest(getQuery, 'Convert a GET query into a POST body', 'postBody');
  doTest(
    siteConfigEntry,
    'Convert a SiteConfig entry into app state',
    'siteConfigState'
  );
});
