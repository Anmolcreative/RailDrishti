javascript
import axios from 'axios';
const API = axios.create({
  baseURL: 'http://localhost:8000'
});

export const getTrains = () => API.get('/trains');
export const optimizeTrains = () => API.post('/optimize');

