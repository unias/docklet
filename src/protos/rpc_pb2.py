# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: rpc.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf.internal import enum_type_wrapper
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
from google.protobuf import descriptor_pb2
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor.FileDescriptor(
  name='rpc.proto',
  package='',
  syntax='proto3',
  serialized_pb=_b('\n\trpc.proto\"f\n\x05Reply\x12\"\n\x06status\x18\x01 \x01(\x0e\x32\x12.Reply.ReplyStatus\x12\x0f\n\x07message\x18\x02 \x01(\t\"(\n\x0bReplyStatus\x12\x0c\n\x08\x41\x43\x43\x45PTED\x10\x00\x12\x0b\n\x07REFUSED\x10\x01\"\'\n\tReportMsg\x12\x1a\n\x08taskmsgs\x18\x01 \x03(\x0b\x32\x08.TaskMsg\"m\n\x07TaskMsg\x12\x0e\n\x06taskid\x18\x01 \x01(\t\x12\x12\n\ninstanceid\x18\x02 \x01(\x05\x12\x1f\n\x0einstanceStatus\x18\x03 \x01(\x0e\x32\x07.Status\x12\r\n\x05token\x18\x04 \x01(\t\x12\x0e\n\x06\x65rrmsg\x18\x05 \x01(\t\"\xc6\x01\n\x08TaskInfo\x12\n\n\x02id\x18\x01 \x01(\t\x12\x10\n\x08username\x18\x02 \x01(\t\x12\x12\n\ninstanceid\x18\x03 \x01(\x05\x12\x15\n\rinstanceCount\x18\x04 \x01(\x05\x12\x15\n\rmaxRetryCount\x18\x05 \x01(\x05\x12\x1f\n\nparameters\x18\x06 \x01(\x0b\x32\x0b.Parameters\x12\x19\n\x07\x63luster\x18\x07 \x01(\x0b\x32\x08.Cluster\x12\x0f\n\x07timeout\x18\x08 \x01(\x05\x12\r\n\x05token\x18\t \x01(\t\"_\n\nParameters\x12\x19\n\x07\x63ommand\x18\x01 \x01(\x0b\x32\x08.Command\x12\x1a\n\x12stderrRedirectPath\x18\x02 \x01(\t\x12\x1a\n\x12stdoutRedirectPath\x18\x03 \x01(\t\"\x8b\x01\n\x07\x43ommand\x12\x13\n\x0b\x63ommandLine\x18\x01 \x01(\t\x12\x13\n\x0bpackagePath\x18\x02 \x01(\t\x12&\n\x07\x65nvVars\x18\x03 \x03(\x0b\x32\x15.Command.EnvVarsEntry\x1a.\n\x0c\x45nvVarsEntry\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\t:\x02\x38\x01\"T\n\x07\x43luster\x12\x15\n\x05image\x18\x01 \x01(\x0b\x32\x06.Image\x12\x1b\n\x08instance\x18\x02 \x01(\x0b\x32\t.Instance\x12\x15\n\x05mount\x18\x03 \x03(\x0b\x32\x06.Mount\"t\n\x05Image\x12\x0c\n\x04name\x18\x01 \x01(\t\x12\x1e\n\x04type\x18\x02 \x01(\x0e\x32\x10.Image.ImageType\x12\r\n\x05owner\x18\x03 \x01(\t\".\n\tImageType\x12\x08\n\x04\x42\x41SE\x10\x00\x12\n\n\x06PUBLIC\x10\x01\x12\x0b\n\x07PRIVATE\x10\x02\"u\n\x05Mount\x12\x10\n\x08provider\x18\x01 \x01(\t\x12\x11\n\tlocalPath\x18\x02 \x01(\t\x12\x12\n\nremotePath\x18\x03 \x01(\t\x12\x11\n\taccessKey\x18\x04 \x01(\t\x12\x11\n\tsecretKey\x18\x05 \x01(\t\x12\r\n\x05other\x18\x06 \x01(\t\"B\n\x08Instance\x12\x0b\n\x03\x63pu\x18\x01 \x01(\x05\x12\x0e\n\x06memory\x18\x02 \x01(\x05\x12\x0c\n\x04\x64isk\x18\x03 \x01(\x05\x12\x0b\n\x03gpu\x18\x04 \x01(\x05*[\n\x06Status\x12\x0b\n\x07WAITING\x10\x00\x12\x0b\n\x07RUNNING\x10\x01\x12\r\n\tCOMPLETED\x10\x02\x12\n\n\x06\x46\x41ILED\x10\x03\x12\x0b\n\x07TIMEOUT\x10\x04\x12\x0f\n\x0bOUTPUTERROR\x10\x05\x32(\n\x06Master\x12\x1e\n\x06report\x12\n.ReportMsg\x1a\x06.Reply\"\x00\x32-\n\x06Worker\x12#\n\x0cprocess_task\x12\t.TaskInfo\x1a\x06.Reply\"\x00\x62\x06proto3')
)

_STATUS = _descriptor.EnumDescriptor(
  name='Status',
  full_name='Status',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='WAITING', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='RUNNING', index=1, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='COMPLETED', index=2, number=2,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='FAILED', index=3, number=3,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='TIMEOUT', index=4, number=4,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='OUTPUTERROR', index=5, number=5,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=1100,
  serialized_end=1191,
)
_sym_db.RegisterEnumDescriptor(_STATUS)

Status = enum_type_wrapper.EnumTypeWrapper(_STATUS)
WAITING = 0
RUNNING = 1
COMPLETED = 2
FAILED = 3
TIMEOUT = 4
OUTPUTERROR = 5


_REPLY_REPLYSTATUS = _descriptor.EnumDescriptor(
  name='ReplyStatus',
  full_name='Reply.ReplyStatus',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='ACCEPTED', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='REFUSED', index=1, number=1,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=75,
  serialized_end=115,
)
_sym_db.RegisterEnumDescriptor(_REPLY_REPLYSTATUS)

_IMAGE_IMAGETYPE = _descriptor.EnumDescriptor(
  name='ImageType',
  full_name='Image.ImageType',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='BASE', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='PUBLIC', index=1, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='PRIVATE', index=2, number=2,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=865,
  serialized_end=911,
)
_sym_db.RegisterEnumDescriptor(_IMAGE_IMAGETYPE)


_REPLY = _descriptor.Descriptor(
  name='Reply',
  full_name='Reply',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='status', full_name='Reply.status', index=0,
      number=1, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='message', full_name='Reply.message', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
    _REPLY_REPLYSTATUS,
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=13,
  serialized_end=115,
)


_REPORTMSG = _descriptor.Descriptor(
  name='ReportMsg',
  full_name='ReportMsg',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='taskmsgs', full_name='ReportMsg.taskmsgs', index=0,
      number=1, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=117,
  serialized_end=156,
)


_TASKMSG = _descriptor.Descriptor(
  name='TaskMsg',
  full_name='TaskMsg',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='taskid', full_name='TaskMsg.taskid', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='instanceid', full_name='TaskMsg.instanceid', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='instanceStatus', full_name='TaskMsg.instanceStatus', index=2,
      number=3, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='token', full_name='TaskMsg.token', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='errmsg', full_name='TaskMsg.errmsg', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=158,
  serialized_end=267,
)


_TASKINFO = _descriptor.Descriptor(
  name='TaskInfo',
  full_name='TaskInfo',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='id', full_name='TaskInfo.id', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='username', full_name='TaskInfo.username', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='instanceid', full_name='TaskInfo.instanceid', index=2,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='instanceCount', full_name='TaskInfo.instanceCount', index=3,
      number=4, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='maxRetryCount', full_name='TaskInfo.maxRetryCount', index=4,
      number=5, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='parameters', full_name='TaskInfo.parameters', index=5,
      number=6, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='cluster', full_name='TaskInfo.cluster', index=6,
      number=7, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='timeout', full_name='TaskInfo.timeout', index=7,
      number=8, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='token', full_name='TaskInfo.token', index=8,
      number=9, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=270,
  serialized_end=468,
)


_PARAMETERS = _descriptor.Descriptor(
  name='Parameters',
  full_name='Parameters',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='command', full_name='Parameters.command', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='stderrRedirectPath', full_name='Parameters.stderrRedirectPath', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='stdoutRedirectPath', full_name='Parameters.stdoutRedirectPath', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=470,
  serialized_end=565,
)


_COMMAND_ENVVARSENTRY = _descriptor.Descriptor(
  name='EnvVarsEntry',
  full_name='Command.EnvVarsEntry',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='key', full_name='Command.EnvVarsEntry.key', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='value', full_name='Command.EnvVarsEntry.value', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=_descriptor._ParseOptions(descriptor_pb2.MessageOptions(), _b('8\001')),
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=661,
  serialized_end=707,
)

_COMMAND = _descriptor.Descriptor(
  name='Command',
  full_name='Command',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='commandLine', full_name='Command.commandLine', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='packagePath', full_name='Command.packagePath', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='envVars', full_name='Command.envVars', index=2,
      number=3, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[_COMMAND_ENVVARSENTRY, ],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=568,
  serialized_end=707,
)


_CLUSTER = _descriptor.Descriptor(
  name='Cluster',
  full_name='Cluster',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='image', full_name='Cluster.image', index=0,
      number=1, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='instance', full_name='Cluster.instance', index=1,
      number=2, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='mount', full_name='Cluster.mount', index=2,
      number=3, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=709,
  serialized_end=793,
)


_IMAGE = _descriptor.Descriptor(
  name='Image',
  full_name='Image',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='Image.name', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='type', full_name='Image.type', index=1,
      number=2, type=14, cpp_type=8, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='owner', full_name='Image.owner', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
    _IMAGE_IMAGETYPE,
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=795,
  serialized_end=911,
)


_MOUNT = _descriptor.Descriptor(
  name='Mount',
  full_name='Mount',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='provider', full_name='Mount.provider', index=0,
      number=1, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='localPath', full_name='Mount.localPath', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='remotePath', full_name='Mount.remotePath', index=2,
      number=3, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='accessKey', full_name='Mount.accessKey', index=3,
      number=4, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='secretKey', full_name='Mount.secretKey', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='other', full_name='Mount.other', index=5,
      number=6, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=913,
  serialized_end=1030,
)


_INSTANCE = _descriptor.Descriptor(
  name='Instance',
  full_name='Instance',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='cpu', full_name='Instance.cpu', index=0,
      number=1, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='memory', full_name='Instance.memory', index=1,
      number=2, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='disk', full_name='Instance.disk', index=2,
      number=3, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
    _descriptor.FieldDescriptor(
      name='gpu', full_name='Instance.gpu', index=3,
      number=4, type=5, cpp_type=1, label=1,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None, file=DESCRIPTOR),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  syntax='proto3',
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=1032,
  serialized_end=1098,
)

_REPLY.fields_by_name['status'].enum_type = _REPLY_REPLYSTATUS
_REPLY_REPLYSTATUS.containing_type = _REPLY
_REPORTMSG.fields_by_name['taskmsgs'].message_type = _TASKMSG
_TASKMSG.fields_by_name['instanceStatus'].enum_type = _STATUS
_TASKINFO.fields_by_name['parameters'].message_type = _PARAMETERS
_TASKINFO.fields_by_name['cluster'].message_type = _CLUSTER
_PARAMETERS.fields_by_name['command'].message_type = _COMMAND
_COMMAND_ENVVARSENTRY.containing_type = _COMMAND
_COMMAND.fields_by_name['envVars'].message_type = _COMMAND_ENVVARSENTRY
_CLUSTER.fields_by_name['image'].message_type = _IMAGE
_CLUSTER.fields_by_name['instance'].message_type = _INSTANCE
_CLUSTER.fields_by_name['mount'].message_type = _MOUNT
_IMAGE.fields_by_name['type'].enum_type = _IMAGE_IMAGETYPE
_IMAGE_IMAGETYPE.containing_type = _IMAGE
DESCRIPTOR.message_types_by_name['Reply'] = _REPLY
DESCRIPTOR.message_types_by_name['ReportMsg'] = _REPORTMSG
DESCRIPTOR.message_types_by_name['TaskMsg'] = _TASKMSG
DESCRIPTOR.message_types_by_name['TaskInfo'] = _TASKINFO
DESCRIPTOR.message_types_by_name['Parameters'] = _PARAMETERS
DESCRIPTOR.message_types_by_name['Command'] = _COMMAND
DESCRIPTOR.message_types_by_name['Cluster'] = _CLUSTER
DESCRIPTOR.message_types_by_name['Image'] = _IMAGE
DESCRIPTOR.message_types_by_name['Mount'] = _MOUNT
DESCRIPTOR.message_types_by_name['Instance'] = _INSTANCE
DESCRIPTOR.enum_types_by_name['Status'] = _STATUS
_sym_db.RegisterFileDescriptor(DESCRIPTOR)

Reply = _reflection.GeneratedProtocolMessageType('Reply', (_message.Message,), dict(
  DESCRIPTOR = _REPLY,
  __module__ = 'rpc_pb2'
  # @@protoc_insertion_point(class_scope:Reply)
  ))
_sym_db.RegisterMessage(Reply)

ReportMsg = _reflection.GeneratedProtocolMessageType('ReportMsg', (_message.Message,), dict(
  DESCRIPTOR = _REPORTMSG,
  __module__ = 'rpc_pb2'
  # @@protoc_insertion_point(class_scope:ReportMsg)
  ))
_sym_db.RegisterMessage(ReportMsg)

TaskMsg = _reflection.GeneratedProtocolMessageType('TaskMsg', (_message.Message,), dict(
  DESCRIPTOR = _TASKMSG,
  __module__ = 'rpc_pb2'
  # @@protoc_insertion_point(class_scope:TaskMsg)
  ))
_sym_db.RegisterMessage(TaskMsg)

TaskInfo = _reflection.GeneratedProtocolMessageType('TaskInfo', (_message.Message,), dict(
  DESCRIPTOR = _TASKINFO,
  __module__ = 'rpc_pb2'
  # @@protoc_insertion_point(class_scope:TaskInfo)
  ))
_sym_db.RegisterMessage(TaskInfo)

Parameters = _reflection.GeneratedProtocolMessageType('Parameters', (_message.Message,), dict(
  DESCRIPTOR = _PARAMETERS,
  __module__ = 'rpc_pb2'
  # @@protoc_insertion_point(class_scope:Parameters)
  ))
_sym_db.RegisterMessage(Parameters)

Command = _reflection.GeneratedProtocolMessageType('Command', (_message.Message,), dict(

  EnvVarsEntry = _reflection.GeneratedProtocolMessageType('EnvVarsEntry', (_message.Message,), dict(
    DESCRIPTOR = _COMMAND_ENVVARSENTRY,
    __module__ = 'rpc_pb2'
    # @@protoc_insertion_point(class_scope:Command.EnvVarsEntry)
    ))
  ,
  DESCRIPTOR = _COMMAND,
  __module__ = 'rpc_pb2'
  # @@protoc_insertion_point(class_scope:Command)
  ))
_sym_db.RegisterMessage(Command)
_sym_db.RegisterMessage(Command.EnvVarsEntry)

Cluster = _reflection.GeneratedProtocolMessageType('Cluster', (_message.Message,), dict(
  DESCRIPTOR = _CLUSTER,
  __module__ = 'rpc_pb2'
  # @@protoc_insertion_point(class_scope:Cluster)
  ))
_sym_db.RegisterMessage(Cluster)

Image = _reflection.GeneratedProtocolMessageType('Image', (_message.Message,), dict(
  DESCRIPTOR = _IMAGE,
  __module__ = 'rpc_pb2'
  # @@protoc_insertion_point(class_scope:Image)
  ))
_sym_db.RegisterMessage(Image)

Mount = _reflection.GeneratedProtocolMessageType('Mount', (_message.Message,), dict(
  DESCRIPTOR = _MOUNT,
  __module__ = 'rpc_pb2'
  # @@protoc_insertion_point(class_scope:Mount)
  ))
_sym_db.RegisterMessage(Mount)

Instance = _reflection.GeneratedProtocolMessageType('Instance', (_message.Message,), dict(
  DESCRIPTOR = _INSTANCE,
  __module__ = 'rpc_pb2'
  # @@protoc_insertion_point(class_scope:Instance)
  ))
_sym_db.RegisterMessage(Instance)


_COMMAND_ENVVARSENTRY.has_options = True
_COMMAND_ENVVARSENTRY._options = _descriptor._ParseOptions(descriptor_pb2.MessageOptions(), _b('8\001'))

_MASTER = _descriptor.ServiceDescriptor(
  name='Master',
  full_name='Master',
  file=DESCRIPTOR,
  index=0,
  options=None,
  serialized_start=1193,
  serialized_end=1233,
  methods=[
  _descriptor.MethodDescriptor(
    name='report',
    full_name='Master.report',
    index=0,
    containing_service=None,
    input_type=_REPORTMSG,
    output_type=_REPLY,
    options=None,
  ),
])
_sym_db.RegisterServiceDescriptor(_MASTER)

DESCRIPTOR.services_by_name['Master'] = _MASTER


_WORKER = _descriptor.ServiceDescriptor(
  name='Worker',
  full_name='Worker',
  file=DESCRIPTOR,
  index=1,
  options=None,
  serialized_start=1235,
  serialized_end=1280,
  methods=[
  _descriptor.MethodDescriptor(
    name='process_task',
    full_name='Worker.process_task',
    index=0,
    containing_service=None,
    input_type=_TASKINFO,
    output_type=_REPLY,
    options=None,
  ),
])
_sym_db.RegisterServiceDescriptor(_WORKER)

DESCRIPTOR.services_by_name['Worker'] = _WORKER

# @@protoc_insertion_point(module_scope)
