const { contextBridge, ipcRenderer } = require('electron');

const invoke = (ch) => (...args) => ipcRenderer.invoke(ch, ...args);
const on = (ch) => (cb) => {
  const listener = (_e, payload) => cb(payload);
  ipcRenderer.on(ch, listener);
  return () => ipcRenderer.removeListener(ch, listener);
};

contextBridge.exposeInMainWorld('tuff', {
  settings: { get: invoke('settings:get'), set: invoke('settings:set') },
  project: { default: invoke('project:default'), openFolder: invoke('dialog:openFolder') },
  fs: {
    readDir: invoke('fs:readDir'),
    listAll: invoke('fs:listAll'),
    readFile: invoke('fs:readFile'),
    writeFile: invoke('fs:writeFile'),
    exists: invoke('fs:exists'),
    createFile: invoke('fs:createFile'),
    createDir: invoke('fs:createDir'),
    rename: invoke('fs:rename'),
    trash: invoke('fs:trash'),
    reveal: invoke('shell:reveal'),
    search: invoke('fs:search'),
    replaceInFile: invoke('fs:replaceInFile'),
  },
  run: { start: invoke('run:start'), stop: invoke('run:stop'), input: invoke('run:input'), onData: on('run:data'), onExit: on('run:exit') },
  build: {
    start: invoke('build:start'),
    cancel: invoke('build:cancel'),
    iconPreview: invoke('build:iconPreview'),
    chooseIcon: invoke('dialog:openImage'),
    openPath: invoke('shell:openPath'),
    onEvent: on('build:event'),
  },
  update: {
    state: invoke('update:state'),
    check: invoke('update:check'),
    install: invoke('update:install'),
    restart: invoke('update:restart'),
    reschedule: invoke('update:reschedule'),
    onStatus: on('update:status'),
  },
  plugins: {
    list: invoke('plugins:list'),
    install: invoke('plugins:install'),
    uninstall: invoke('plugins:uninstall'),
    setEnabled: invoke('plugins:setEnabled'),
  },
  agents: {
    detect: invoke('agents:detect'),
    connection: invoke('agents:connection'),
    connect: invoke('agents:connect'),
    mcpServer: invoke('agents:mcpServer'),
    run: invoke('agents:run'),
    stop: invoke('agents:stop'),
    onEvent: on('agents:event'),
  },
  version: invoke('app:version'),
  checkSource: invoke('tuff:check'),
  openRepo: (url) => ipcRenderer.invoke('shell:openExternal', url),
  win: {
    minimize: invoke('window:minimize'),
    toggleMaximize: invoke('window:toggleMaximize'),
    close: invoke('window:close'),
    isMaximized: invoke('window:isMaximized'),
    onMaximized: on('window:maximized'),
    onBlur: on('window:blur'),
    devtools: invoke('app:devtools'),
  },
  platform: process.platform,
  sep: process.platform === 'win32' ? '\\' : '/',
});
