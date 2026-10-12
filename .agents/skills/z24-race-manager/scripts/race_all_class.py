#!/usr/bin/env python3
from race_live_common import worker_main, endpoint_once
if __name__=='__main__':
    worker_main('all_class',lambda config:endpoint_once(config,'all_class'))
