import { answer } from '../../../../_api.js';
import { aggregateQuery } from '../../../../_query.js';

// Counts, sums, averages, minimums and maximums by group over the newest loaded version.
export const onRequestGet = (context) => answer(context, aggregateQuery, 'aggregate');
