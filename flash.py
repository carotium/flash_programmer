import time
import spidev
import RPi.GPIO as GPIO
import argparse
import numpy as np

READ_ID 				= 0x9E
READ 					= 0x03
PAGE_PROGRAM 			= 0x02
WRITE_ENABLE			= 0x06
READ_STATUS_REGISTER 	= 0x05
_4KB_SECTOR_ERASE 		= 0x20

CS = 25

bus = 0
device = 0
spi = spidev.SpiDev()

spi.open(bus, device)

spi.max_speed_hz = 500000
spi.mode = spi.no_cs

GPIO.setmode(GPIO.BCM)
GPIO.setup(CS, GPIO.OUT)
GPIO.output(CS,1)

def slave_select():
	GPIO.output(CS, 0)

def slave_unselect():
	GPIO.output(CS, 1)

def flash_send(command, address = None):
	spi.writebytes2([command])
	if(address != None):
		spi.writebytes2(address)

def flash_read(read_bytes, address = None):
	if(address != None):
		spi.writebytes2(address)
	data = spi.readbytes(read_bytes)
	
	return data

def flash_read_contents(line_count):
	print(f"Sending Read")
	slave_select()
	flash_send(command=READ, address=[0x00, 0x00, 0x00])

	data = []

	for i in range(line_count):
		data.append(flash_read(read_bytes=4))

	slave_unselect()

	for i in range(line_count):
		byte = []
		for data_byte in data[i]:
			data_byte = f"{data_byte:02X}"
			byte.append(data_byte)
		print(f"{i*4}: {byte[0]}{byte[1]}{byte[2]}{byte[3]}")

	return data


def hex_add_header(input_hex, mod_hex_out = 'output.hex'):
    with open(input_hex, 'r') as f:
        lines = f.readlines()
				
    line_count = len(lines)
	
    with open(mod_hex_out, 'w') as o:
        o.write(f"{line_count:08X}\n")
        o.writelines(lines)

    return line_count, lines
	
def read_hex(output_file):
	# print(f"Reading output file")
	with open(output_file, 'r') as f:
		count = f.readline()
		count = int(count, 16)
		# print(f"This many lines to write: {count}")
		return count
	
def flash_page_program(f, count = 64, address=[0x00, 0x00, 0x00]):
	print(f"This many lines to write: {count}")
	address_num = int.from_bytes(address)
	
	time.sleep(1)
	status_reg = flash_read_status_register()
	while(status_reg[0] != 2):
		print(f"Reading status register: {status_reg[0]}")
		print(f"Sending write enable")
		flash_write_enable()
		time.sleep(1)
		status_reg = flash_read_status_register()
	print(f"Sending page program")
	slave_select()
	flash_send(command=PAGE_PROGRAM, address=address)
	print(f"Programming flash at {address_num}:")
	for i in range(count):
		data = f.readline()
		data = int(data, 16)
		print(f"{address_num+i*4}: {data:08X}")
		data = data.to_bytes(4)
		flash_send(data[3])
		flash_send(data[2])
		flash_send(data[1])
		flash_send(data[0])

		#if(i == 98):
			#import pdb; pdb.set_trace()


	slave_unselect()

def program_hex_to_flash(output_file):
	with open(output_file, 'r') as f:
		count = f.readline()
		count = int(count, 16)

		address_bytes = 0
		address = address_bytes.to_bytes(3)

		#import pdb; pdb.set_trace()

		# Program the first word with number of words

		f.seek(0)

		count += 1

		while(count*4 >= 256):
			flash_page_program(f, address=address)			
			count -= 64
			address_bytes += 256
			address = address_bytes.to_bytes(3)

		if(count != 0):
			flash_page_program(f, count=count, address=address)

# def flash_startup(args):
# 	line_count = process_hex(args.file, args.output)
# 	return line_count

def flash_erase_4KB(address):
	slave_select()
	flash_send(_4KB_SECTOR_ERASE, address=address)
	slave_unselect()

def flash_write_enable():
	slave_select()
	flash_send(WRITE_ENABLE)
	slave_unselect()

def flash_read_status_register():
	slave_select()
	flash_send(READ_STATUS_REGISTER)
	status_register = flash_read(1)
	slave_unselect()

	return status_register

def flash_program(count, address):
	slave_select()
	flash_send(PAGE_PROGRAM, address=address)
	num = count.to_bytes(4)

	flash_send(num[3])
	flash_send(num[2])
	flash_send(num[1])
	flash_send(num[0])

	# for i in range(count):
	# 	data = f.readline()
	# 	data = int(data, 16)
	# 	data = data.to_bytes(4)
	# 	flash_send(data[3])
	# 	flash_send(data[2])
	# 	flash_send(data[1])
	# 	flash_send(data[0])

	slave_unselect()

def main():

	parser = argparse.ArgumentParser(description='Process input HEX file for write to flash')
	parser.add_argument('-i', '--input', required=True, help='Path to the input hex file')
	parser.add_argument('-o', '--mod_hex_out', default='output.hex' , required=False, help='Path to the output hex file')
	parser.add_argument('-r', '--read', default=False)
	args = parser.parse_args()

	line_count = 0

	if(not args.read):
		line_count, hex_data = hex_add_header(args.input, args.mod_hex_out)

	print(f"Sending write enable")
	flash_write_enable()
	print(f"Status register: {flash_read_status_register()}")
	print(f"Sending erase 4KB")
	flash_erase_4KB(address=[0x00, 0x00, 0x00])

	assert line_count < 1024

	time.sleep(2)
	print(f"Done erasing!")

	flash_read_contents(line_count+1)

	print(f"Programming flash with input hex file")

	program_hex_to_flash(args.mod_hex_out)

	time.sleep(2)
	print(f"Done programming!")

	print(f"Sending Read")
	slave_select()
	#flash_send(command=READ, address=[0x00, 0x00, 0x00])

	new_data = flash_read_contents(line_count+1)

	hex_data_old = []
	
	line_count_word = []
	line_count_word.append(line_count.to_bytes(4)[3])
	line_count_word.append(line_count.to_bytes(4)[2])
	line_count_word.append(line_count.to_bytes(4)[1])
	line_count_word.append(line_count.to_bytes(4)[0])

	hex_data_old.append(line_count_word)

	for i in range(line_count):
		byte = []
		#import pdb; pdb.set_trace()

		byte.append(int(hex_data[i].strip('\n')[6:8], 16))
		byte.append(int(hex_data[i].strip('\n')[4:6], 16))
		byte.append(int(hex_data[i].strip('\n')[2:4], 16))
		byte.append(int(hex_data[i].strip('\n')[0:2], 16))

		hex_data_old.append(byte)

	if new_data != hex_data_old:
		print(f"Mismatch!")
		import pdb; pdb.set_trace()

if __name__ == "__main__":
	main()
