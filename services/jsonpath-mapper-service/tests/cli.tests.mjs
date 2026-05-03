import { expect } from 'chai';
import { execFileSync, execSync } from 'node:child_process';
import { writeFileSync, readFileSync, unlinkSync, mkdtempSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

const CLI = 'src/cli.ts';
const run = (args, opts = {}) =>
  execFileSync('npx', ['tsx', CLI, ...args], {
    encoding: 'utf-8',
    cwd: new URL('..', import.meta.url).pathname,
    ...opts,
  });

const runFail = (args, opts = {}) => {
  try {
    run(args, { ...opts, stdio: ['pipe', 'pipe', 'pipe'] });
    throw new Error('Expected command to fail');
  } catch (err) {
    if (err.message === 'Expected command to fail') throw err;
    return { status: err.status, stderr: err.stderr?.toString() ?? '', stdout: err.stdout?.toString() ?? '' };
  }
};

let tmpDir;

before(() => {
  tmpDir = mkdtempSync(join(tmpdir(), 'cli-test-'));
});

const writeJson = (name, obj) => {
  const p = join(tmpDir, name);
  writeFileSync(p, JSON.stringify(obj));
  return p;
};

describe('CLI', () => {
  describe('basic mapping', () => {
    it('should map data using a template', () => {
      const dataFile = writeJson('data.json', {
        user: { firstName: 'Alice', lastName: 'Smith', address: { city: 'Vienna' } },
      });
      const templateFile = writeJson('template.json', {
        name: '.user.firstName',
        surname: '.user.lastName',
        city: '.user.address.city',
      });

      const stdout = run([dataFile, templateFile]);
      const result = JSON.parse(stdout);

      expect(result).to.deep.equal({
        name: 'Alice',
        surname: 'Smith',
        city: 'Vienna',
      });
    });

    it('should handle nested template objects', () => {
      const dataFile = writeJson('nested-data.json', {
        books: [
          { title: 'Clean Code', author: { name: 'Robert C. Martin' }, price: 17.96 },
          { title: 'The Good Parts', author: { name: 'Douglas Crockford' }, price: 15.67 },
        ],
      });
      const templateFile = writeJson('nested-template.json', {
        allTitles: '.books[*].title',
        firstAuthor: '.books[0].author.name',
      });

      const result = JSON.parse(run([dataFile, templateFile]));

      expect(result.allTitles).to.deep.equal(['Clean Code', 'The Good Parts']);
      expect(result.firstAuthor).to.equal('Robert C. Martin');
    });
  });

  describe('-o / --output flag', () => {
    it('should write result to the specified output file', () => {
      const dataFile = writeJson('out-data.json', { value: 42 });
      const templateFile = writeJson('out-template.json', { num: '.value' });
      const outFile = join(tmpDir, 'result.json');

      run([dataFile, templateFile, '-o', outFile]);

      const written = JSON.parse(readFileSync(outFile, 'utf-8'));
      expect(written).to.deep.equal({ num: 42 });
    });

    it('should also work with --output', () => {
      const dataFile = writeJson('out2-data.json', { x: 'hello' });
      const templateFile = writeJson('out2-template.json', { msg: '.x' });
      const outFile = join(tmpDir, 'result2.json');

      run([dataFile, templateFile, '--output', outFile]);

      const written = JSON.parse(readFileSync(outFile, 'utf-8'));
      expect(written).to.deep.equal({ msg: 'hello' });
    });
  });

  describe('--help flag', () => {
    it('should print usage and exit with code 1', () => {
      const { status, stderr } = runFail(['--help']);
      expect(status).to.equal(1);
      expect(stderr).to.include('Usage: jsonpath-mapper');
    });

    it('should print usage with -h', () => {
      const { stderr } = runFail(['-h']);
      expect(stderr).to.include('Usage: jsonpath-mapper');
    });
  });

  describe('error handling', () => {
    it('should fail with no arguments', () => {
      const { status, stderr } = runFail([]);
      expect(status).to.equal(1);
      expect(stderr).to.include('Usage:');
    });

    it('should fail when data file does not exist', () => {
      const templateFile = writeJson('err-template.json', { a: '.b' });
      const { status, stderr } = runFail(['/tmp/nonexistent-data-12345.json', templateFile]);
      expect(status).to.equal(1);
      expect(stderr).to.include('Error reading data file');
    });

    it('should fail when template file does not exist', () => {
      const dataFile = writeJson('err-data.json', { b: 1 });
      const { status, stderr } = runFail([dataFile, '/tmp/nonexistent-template-12345.json']);
      expect(status).to.equal(1);
      expect(stderr).to.include('Error reading template file');
    });

    it('should fail when data file contains invalid JSON', () => {
      const badFile = join(tmpDir, 'bad.json');
      writeFileSync(badFile, '{ not valid json }');
      const templateFile = writeJson('err2-template.json', { a: '.b' });
      const { status, stderr } = runFail([badFile, templateFile]);
      expect(status).to.equal(1);
      expect(stderr).to.include('Error reading data file');
    });

    it('should fail when -o is missing its argument', () => {
      const dataFile = writeJson('err3-data.json', { x: 1 });
      const templateFile = writeJson('err3-template.json', { y: '.x' });
      const { status, stderr } = runFail([dataFile, templateFile, '-o']);
      expect(status).to.equal(1);
      expect(stderr).to.include('-o requires a file path');
    });
  });
});
