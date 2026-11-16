import { expect } from 'chai';
import serverModule from '../src/api/server.ts';

const { buildServer } = serverModule;

describe('API', () => {
  let server;

  before(async () => {
    server = await buildServer();
    await server.ready();
  });

  after(async () => {
    await server.close();
  });

  for (const url of ['/map', '/map/async']) {
    it(`maps data through ${url}`, async () => {
      const response = await server.inject({
        method: 'POST',
        url,
        payload: { data: { value: 42 }, template: { number: '.value' } },
      });
      expect(response.statusCode).to.equal(200);
      expect(response.json()).to.deep.equal({ result: { number: 42 } });
    });

    it(`maps JSONPath filters through ${url}`, async () => {
      const response = await server.inject({
        method: 'POST',
        url,
        payload: {
          data: { items: [{ price: 5, name: 'low' }, { price: 25, name: 'high' }] },
          template: { names: 'items[?(@.price < 20)].name' },
        },
      });
      expect(response.statusCode).to.equal(200);
      expect(response.json()).to.deep.equal({ result: { names: ['low'] } });
    });

    it(`blocks CVE-2025-1302 without executing code at ${url}`, async () => {
      const marker = '__jsonpathMapperCVE20251302Api__';
      const query = `..[?(p="globalThis.${marker}=true";a=''[['constructor']][['constructor']](p);a())]`;
      try {
        const response = await server.inject({
          method: 'POST',
          url,
          payload: { data: { a: 1 }, template: { value: query } },
        });
        expect(globalThis[marker]).to.be.undefined;
        expect(response.statusCode).to.equal(500);
        expect(response.json().message).to.include('Mapping failed:');
      } finally {
        delete globalThis[marker];
      }
    });

    it(`validates requests to ${url}`, async () => {
      const response = await server.inject({ method: 'POST', url, payload: {} });
      expect(response.statusCode).to.equal(400);
    });

    it(`handles invalid JSONPath at ${url}`, async () => {
      const response = await server.inject({
        method: 'POST',
        url,
        payload: { data: { value: 42 }, template: { number: '[?(' } },
      });
      expect(response.statusCode).to.equal(500);
      expect(response.json().message).to.include('Mapping failed:');
    });
  }
});
