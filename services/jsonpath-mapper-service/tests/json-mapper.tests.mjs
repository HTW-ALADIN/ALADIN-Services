import { expect } from 'chai';
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

// When the project runtime (or build) resolves the ES modules
// or if the package.json "type" is "module"
// this is the intended way to import the mapJson methods
import mapJson, { mapJsonAsync } from 'jsonpath-mapper';

// // When the project runtime resolves the Common JS modules (standard Node.js resolution)
// // we cannot import the default and named exports 
// // instead import everything and destructure the required method
// import pkg from 'jsonpath-mapper';
// const { default: mapJson, mapJsonAsync } = pkg;

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
