// Starts the reader on the made-up demo threads. The Mac helper will serve its own start file with real ones.
import { mount } from './reader.js';
import { DEMO_THREADS, DEMO_WORDS } from './demo.js';

mount(document.getElementById('app'), { words: DEMO_WORDS, threads: DEMO_THREADS }, { demo: true });
