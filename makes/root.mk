SHELL := /bin/sh
.SHELLFLAGS := -eu -c
.DEFAULT_GOAL := help

include makes/help.mk
include makes/bijux-std.mk
include makes/bijux-docs.mk
