import { answer } from '../../../../../../_api.js';
import { aggregateQuery } from '../../../../../../_query.js';

// Aggregates over one dated version, cached for good.
export const onRequestGet = (context) => answer(context, aggregateQuery, 'aggregate');
