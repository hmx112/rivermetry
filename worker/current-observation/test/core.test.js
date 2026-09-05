import test from 'node:test';
import assert from 'node:assert/strict';
import {CACHE_SECONDS,freshness,parseUSGSFeatures} from '../src/core.js';

test('cache is 900 seconds',()=>assert.equal(CACHE_SECONDS,900));
test('maps gage and flow',()=>{const data=parseUSGSFeatures([{properties:{parameter_code:'00065',value:'4.2',unit_of_measure:'ft',time:'2026-09-05T00:00:00Z'}},{properties:{parameter_code:'00060',value:'300',unit_of_measure:'ft^3/s',time:'2026-09-05T00:00:00Z'}}]);assert.equal(data.water_level.value,4.2);assert.equal(data.streamflow.value,300);});
test('freshness states',()=>{const now=Date.parse('2026-09-05T01:00:00Z');assert.equal(freshness('2026-09-05T00:45:00Z',now),'fresh');assert.equal(freshness('2026-09-05T00:00:00Z',now),'delayed');assert.equal(freshness('2026-09-04T23:00:00Z',now),'unavailable');});
