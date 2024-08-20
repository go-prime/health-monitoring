import os
import psutil


def get_ram_usage():
    return psutil.virtual_memory()


def get_cpu_usage():
    return {
        "cpu_usage": psutil.cpu_percent(interval=1)
    }


def get_disk_usage():
    hdd = psutil.disk_usage('/')
    return {
        "used": round(hdd.used / (2**30), 2),
        "free": round(hdd.free / (2**30), 2)
    }


def get_load_average():
    '''Represents the processes which are in a runnable state,
        either using the CPU or waiting to use the CPU'''
    five, ten, fifteen = psutil.getloadavg()
    return {
        "Last 5 Mins": five,
        "Last 10 Mins": ten,
        "Last 15 Mins": fifteen,
    }


if __name__ == "__main__":
    print(get_load_average())
