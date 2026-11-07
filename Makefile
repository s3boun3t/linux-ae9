.DEFAULT_GOAL := all
KERNEL_RELEASE ?= $(shell uname -r)
KDIR ?= /lib/modules/$(KERNEL_RELEASE)/build
.PHONY: all clean
all:
	python3 build.py build --kernel-release "$(KERNEL_RELEASE)" --kdir "$(KDIR)"
clean:
	python3 build.py clean --kernel-release "$(KERNEL_RELEASE)" --kdir "$(KDIR)"
