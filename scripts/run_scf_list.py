import runpy
import asyncio
import json
import sys

def main():
    try:
        g = runpy.run_path('spark-framework-engine.py')
        f = g.get('scf_list_available_packages')
        if f is None:
            print(json.dumps({'ok': False, 'error': 'scf_list_available_packages not found'}), flush=True)
            sys.exit(2)
        result = asyncio.run(f())
        print(json.dumps({'ok': True, 'result': result}, ensure_ascii=False), flush=True)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(json.dumps({'ok': False, 'error': str(e), 'traceback': tb}, ensure_ascii=False), flush=True)
        sys.exit(1)

if __name__ == '__main__':
    main()
