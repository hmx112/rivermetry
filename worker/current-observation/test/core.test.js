import test from 'node:test';
import assert from 'node:assert/strict';
import {CACHE_SECONDS,calculateTrend,freshness,parseUSGSFeatures} from '../src/core.js';

test('cache is 900 seconds',()=>assert.equal(CACHE_SECONDS,900));
test('maps gage and flow using newest record per parameter',()=>{const data=parseUSGSFeatures([{properties:{parameter_code:'00065',value:'4.3',unit_of_measure:'ft',time:'2026-09-05T01:00:00Z'}},{properties:{parameter_code:'00065',value:'4.2',unit_of_measure:'ft',time:'2026-09-05T00:45:00Z'}},{properties:{parameter_code:'00060',value:'300',unit_of_measure:'ft3/s',time:'2026-09-05T01:00:00Z'}}]);assert.equal(data.water_level.value,4.3);assert.equal(data.streamflow.value,300);assert.equal(data.observed_at,'2026-09-05T01:00:00Z');});
test('freshness states',()=>{const now=Date.parse('2026-09-05T01:00:00Z');assert.equal(freshness('2026-09-05T00:45:00Z',now),'fresh');assert.equal(freshness('2026-09-05T00:00:00Z',now),'delayed');assert.equal(freshness('2026-09-04T23:00:00Z',now),'unavailable');});
test('trend uses 60 minute gage window and 0.03 ft deadband',()=>{const rising=[{properties:{parameter_code:'00065',value:'4.20',time:'2026-09-05T00:00:00Z'}},{properties:{parameter_code:'00065',value:'4.26',time:'2026-09-05T01:00:00Z'}}];const steady=[{properties:{parameter_code:'00065',value:'4.20',time:'2026-09-05T00:00:00Z'}},{properties:{parameter_code:'00065',value:'4.22',time:'2026-09-05T01:00:00Z'}}];assert.equal(calculateTrend(rising),'rising');assert.equal(calculateTrend(steady),'steady');assert.equal(calculateTrend([]),'unknown');});
