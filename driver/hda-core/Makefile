snd-hda-core-y := hda_bus_type.o bus.o device.o sysfs.o \
	regmap.o controller.o stream.o array.o hdmi_chmap.o
snd-hda-core-y += trace.o
CFLAGS_trace.o := -I$(src)
snd-hda-core-$(CONFIG_SND_HDA_COMPONENT) += component.o
snd-hda-core-$(CONFIG_SND_HDA_I915) += i915.o
obj-m += snd-hda-core.o
