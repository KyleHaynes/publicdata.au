import { answer } from '../../../../_api.js';
import { rowsQuery } from '../../../../_query.js';

// Rows of the newest loaded version, filtered and paged.
export const onRequestGet = (context) => answer(context, rowsQuery, 'rows');
