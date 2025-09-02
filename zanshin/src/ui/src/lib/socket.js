import { io } from 'socket.io-client';

export const socket = io('/', {
    autoConnect: false,
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 100,
    reconnectionDelayMax: 5000,
    timeout: 20000,
    transports: ['websocket'],
    path: '/socket.io/'
});