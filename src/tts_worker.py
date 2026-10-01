"""Keep model inference independent of the RTC event loop and its Python threads."""
import concurrent.futures
import multiprocessing


def inference_worker(connection,cancel,config):
    from tts_bridge_server import create_engine
    engine=create_engine(config)
    try:
        engine.initialize()
        engine.generate('안녕!',lambda pcm:None,lambda:False)
        connection.send(('ready',None))
        while True:
            text=connection.recv()
            if text is None:break
            try:
                result=engine.generate(text,lambda pcm:connection.send(('pcm',pcm)),cancel.is_set)
                connection.send(('done',result))
            except Exception as error:
                connection.send(('error',f'{type(error).__name__}: {error}'))
    except (EOFError,KeyboardInterrupt):pass
    except Exception as error:
        connection.send(('error',f'{type(error).__name__}: {error}'))
    finally:
        connection.close();engine.shutdown()


class ProcessEngine:
    def __init__(self,config,worker=inference_worker):
        self.config=config;self.worker=worker;self.process=None;self.connection=None
        self.context=multiprocessing.get_context('spawn')
        self.cancel=self.context.Event()
        self.executor=concurrent.futures.ThreadPoolExecutor(max_workers=1,thread_name_prefix='dots-tts-ipc')

    def initialize(self):
        self.connection,child=self.context.Pipe()
        self.process=self.context.Process(target=self.worker,args=(child,self.cancel,self.config),daemon=True)
        self.process.start();child.close()
        try:
            if not self.connection.poll(self.config.get('workerStartupTimeoutSeconds',180)):
                raise TimeoutError('Voice worker did not start')
            kind,payload=self.connection.recv()
            if kind!='ready':raise RuntimeError(payload)
        except BaseException:
            self.process.terminate();self.process.join(2);self.connection.close()
            self.connection=None
            raise

    def generate(self,text,emit,cancelled):
        self.cancel.clear()
        self.connection.send(text)
        while True:
            if cancelled():self.cancel.set()
            if not self.connection.poll(0.02):
                if not self.process.is_alive():raise RuntimeError('Voice worker stopped')
                continue
            kind,payload=self.connection.recv()
            if kind=='pcm':
                if not self.cancel.is_set() and not cancelled():emit(payload)
            elif kind=='done':return None if self.cancel.is_set() or cancelled() else payload
            elif kind=='error':raise RuntimeError(payload)

    def shutdown(self):
        self.cancel.set()
        self.executor.shutdown(wait=True,cancel_futures=True)
        if self.connection:
            if self.process and self.process.is_alive():
                try:self.connection.send(None)
                except (BrokenPipeError,EOFError,OSError):pass
                self.process.join(5)
                if self.process.is_alive():self.process.terminate();self.process.join(2)
            self.connection.close()
